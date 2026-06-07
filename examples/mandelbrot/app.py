"""
Mandelbrot tile renderer — example for ginext.

It exists to pin down the API surface and the threading shape ginext
supports.

Why this app:

  The Mandelbrot inner loop (`escape_iter`) is pure Python float math.
  Under the GIL it serializes — N worker threads run at ~1x single-thread
  throughput regardless of core count. Under free-threaded Python 3.14
  (`python3.14t`, PEP 703), the same code scales linearly with cores
  because each thread can hold the bytecode interpreter independently.

  The window's header bar shows tiles/sec and the GIL state, so running
  the same binary against `python3.14` (GIL on) vs `python3.14t`
  (GIL off) makes the difference obvious without any other tooling.

Threading shape:

  - One main thread runs the GTK main loop.
  - N worker threads (= os.cpu_count()) compute tiles drawn from a
    queue. Each tile is computed entirely inside Python — no numpy,
    no C extensions doing the heavy lifting. This is on purpose:
    we want the demo to fail under the GIL.
  - Workers post finished tiles back via a queue. A GLib idle handler
    drains the queue on the main thread and blits tiles into a shared
    RGBA buffer that backs a Gdk.MemoryTexture.
  - Pan/zoom bumps a generation counter; workers check it between
    tiles and abandon stale work.

Run:
    uv run --python 3.14   python examples/mandelbrot/app.py    # GIL on  — slow
    uv run --python 3.14t  python examples/mandelbrot/app.py    # GIL off — scales
"""

from __future__ import annotations

import os
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass

from ginext import Gdk, Gio, GLib, GLibUnix, Gtk


INITIAL_WIDTH = 1024
INITIAL_HEIGHT = 768
# WIDTH / HEIGHT are mutated as the window resizes. Workers and helpers
# read them via the local hoists at the start of each render.
WIDTH = INITIAL_WIDTH
HEIGHT = INITIAL_HEIGHT
TILE = 32
MAX_ITER = 384
# Sweet spot from benchmark: ~12 workers gets 5.7× over single-threaded;
# more than that yields no further gain on a 1024×768 / 64-tile image.
WORKERS = min(os.cpu_count() or 4, 20)


# ---------------------------------------------------------------------------
# Pure-Python Mandelbrot kernel. Deliberately not vectorized: this is the
# CPU-bound work we want to parallelize across threads.
#
# Optimizations layered on top of the textbook iteration:
#   - Cardioid + period-2 bulb early-exit. The main set covers a sizable
#     fraction of any centered view; two cheap polynomial tests skip the
#     iteration loop entirely for points known to be inside.
#   - Periodicity (cycle) detection. Trapped orbits never escape; we
#     check `(x, y)` against a stored reference every 32 iterations and
#     return MAX_ITER early when stuck.
#   - Precomputed RGBA palette (a `bytes` of length 4*MAX_ITER). The
#     worker writes a 4-byte slice per pixel instead of unpacking and
#     storing four values.
# ---------------------------------------------------------------------------


def escape_iter(cx: float, cy: float, max_iter: int = MAX_ITER) -> int:
    # Main cardioid: q = (cx - 1/4)^2 + cy^2; inside iff q*(q + cx - 1/4) < cy^2/4
    cx_q = cx - 0.25
    cy2 = cy * cy
    q = cx_q * cx_q + cy2
    if q * (q + cx_q) < 0.25 * cy2:
        return max_iter
    # Period-2 bulb: (cx + 1)^2 + cy^2 < 1/16
    dx = cx + 1.0
    if dx * dx + cy2 < 0.0625:
        return max_iter

    x = y = 0.0
    # Periodicity check state.
    ref_x, ref_y = 0.0, 0.0
    period_check_at = 32
    period_count = 0

    for i in range(max_iter):
        x2 = x * x
        y2 = y * y
        if x2 + y2 > 4.0:
            return i
        y = 2.0 * x * y + cy
        x = x2 - y2 + cx
        # Compare against reference; if equal, we're trapped.
        if x == ref_x and y == ref_y:
            return max_iter
        period_count += 1
        if period_count >= period_check_at:
            ref_x, ref_y = x, y
            period_count = 0
            period_check_at *= 2  # exponential back-off
    return max_iter


def _build_palette_bytes() -> bytes:
    """Pre-render an RGBA byte string indexed by escape count.
    `_PALETTE[4*i : 4*i+4]` is the RGBA8888 for iteration count i."""
    buf = bytearray(4 * (MAX_ITER + 1))
    for i in range(MAX_ITER + 1):
        if i >= MAX_ITER:
            r = g = b = 0
        else:
            t = i / MAX_ITER
            mt = 1.0 - t
            r = int(9.0 * mt * t * t * t * 255)
            g = int(15.0 * mt * mt * t * t * 255)
            b = int(8.5 * mt * mt * mt * t * 255)
        off = 4 * i
        buf[off] = r & 0xFF
        buf[off + 1] = g & 0xFF
        buf[off + 2] = b & 0xFF
        buf[off + 3] = 0xFF
    return bytes(buf)


_PALETTE = _build_palette_bytes()


# ---------------------------------------------------------------------------
# Viewport: thread-shared but only mutated on the main thread. Workers read
# the snapshot stored on the Tile they pulled from the queue, so we don't
# need a lock here in steady state.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Viewport:
    cx: float
    cy: float
    scale: float
    generation: int

    def pixel_to_complex(self, px: int, py: int) -> tuple[float, float]:
        x = self.cx + (px - WIDTH / 2) * self.scale
        y = self.cy + (py - HEIGHT / 2) * self.scale
        return (x, y)


@dataclass
class Tile:
    tx: int
    ty: int
    w: int
    h: int
    viewport: Viewport


@dataclass
class FinishedTile:
    tile: Tile
    pixels: bytes
    compute_ms: float


# ---------------------------------------------------------------------------
# Worker pool. No GIL = each worker gets a real core.
# ---------------------------------------------------------------------------


class RenderPool:
    def __init__(self, n_workers: int) -> None:
        self._jobs: queue.Queue[Tile | None] = queue.Queue()
        self._done: queue.Queue[FinishedTile] = queue.Queue()
        self._stop = threading.Event()
        # `_gen_view` is a one-element list used as a lock-free atomic
        # cell: the main thread writes index 0, workers read it. Both
        # are atomic in CPython under GIL and nogil; we only need
        # publication ordering for staleness, not exclusion.
        self._gen_view: list[int] = [0]
        self.tiles_finished = 0
        self.threads = [
            threading.Thread(target=self._run, name=f"mandel-{i}", daemon=True)
            for i in range(n_workers)
        ]
        for t in self.threads:
            t.start()

    def submit(self, tile: Tile) -> None:
        self._jobs.put(tile)

    def shutdown(self) -> None:
        self._stop.set()
        for _ in self.threads:
            self._jobs.put(None)

    def set_generation(self, gen: int) -> None:
        self._gen_view[0] = gen

    def drain_finished(self, max_items: int = 64) -> list[FinishedTile]:
        out: list[FinishedTile] = []
        for _ in range(max_items):
            try:
                out.append(self._done.get_nowait())
            except queue.Empty:
                break
        return out

    def _run(self) -> None:
        # Hoist module-level lookups into worker locals — these never change.
        kernel = escape_iter
        palette = _PALETTE
        WIDTH_ = WIDTH
        HEIGHT_ = HEIGHT
        # Reading a list element is atomic under both GIL and nogil — no
        # mutex needed for staleness checks. set_generation publishes by
        # writing to index 0; workers read index 0.
        gen_view = self._gen_view

        while not self._stop.is_set():
            tile = self._jobs.get()
            if tile is None:
                return
            if tile.viewport.generation != gen_view[0]:
                continue
            t0 = time.perf_counter()
            tile_w = tile.w
            tile_h = tile.h
            tx = tile.tx
            ty = tile.ty
            buf = bytearray(tile_w * tile_h * 4)
            vp = tile.viewport
            vp_cx = vp.cx
            vp_cy = vp.cy
            vp_scale = vp.scale
            vp_gen = vp.generation

            half_w = WIDTH_ / 2
            half_h = HEIGHT_ / 2
            stale = False
            i = 0
            for py in range(ty, ty + tile_h):
                # Cancellation check once per row, lock-free.
                if gen_view[0] != vp_gen:
                    stale = True
                    break
                cy = vp_cy + (py - half_h) * vp_scale
                row_off = i
                for px in range(tx, tx + tile_w):
                    cx = vp_cx + (px - half_w) * vp_scale
                    n = kernel(cx, cy)
                    p = 4 * n
                    buf[row_off] = palette[p]
                    buf[row_off + 1] = palette[p + 1]
                    buf[row_off + 2] = palette[p + 2]
                    buf[row_off + 3] = palette[p + 3]
                    row_off += 4
                i += tile_w * 4
            if not stale:
                dt = (time.perf_counter() - t0) * 1000.0
                self._done.put(FinishedTile(tile, bytes(buf), dt))
                self.tiles_finished += 1


# ---------------------------------------------------------------------------
# Rendering surface — owned by the main thread, blitted into from the idle
# handler that drains the worker output queue.
# ---------------------------------------------------------------------------


class Surface:
    def __init__(self, w: int, h: int) -> None:
        self.w = w
        self.h = h
        self.stride = w * 4
        self.buf = bytearray(w * h * 4)

    def blit(self, ft: FinishedTile) -> None:
        t = ft.tile
        src = ft.pixels
        for row in range(t.h):
            dst_off = (t.ty + row) * self.stride + t.tx * 4
            src_off = row * t.w * 4
            self.buf[dst_off : dst_off + t.w * 4] = src[src_off : src_off + t.w * 4]

    def to_texture(self) -> Gdk.Texture:
        # Wrap the buffer in a GLib.Bytes so the texture owns a reference to
        # the pixel data; passing a bare `bytes` lets it be freed while GTK
        # is still compositing the previous frame (segfault under repeated
        # set_paintable).
        return Gdk.MemoryTexture.new(
            self.w,
            self.h,
            Gdk.MemoryFormat.R8G8B8A8,
            GLib.Bytes.new(bytes(self.buf)),
            self.stride,
        )


# ---------------------------------------------------------------------------
# Main window. All GTK calls happen on the main thread.
# ---------------------------------------------------------------------------


class MandelbrotWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application) -> None:
        super().__init__(
            application=application,
            title="ginext mandelbrot",
            default_width=INITIAL_WIDTH,
            default_height=INITIAL_HEIGHT + 48,
        )

        self.surface = Surface(WIDTH, HEIGHT)
        self.viewport = Viewport(cx=-0.5, cy=0.0, scale=3.5 / WIDTH, generation=0)
        self.pool = RenderPool(WORKERS)

        self._stat_window: list[tuple[float, int]] = []
        self._last_stat_count = 0

        self._build_ui()
        self._enqueue_all_tiles()

        GLib.timeout_add(33, self._drain_and_present)
        GLib.timeout_add(500, self._update_status)

    def _build_ui(self) -> None:
        header = Gtk.HeaderBar()
        gil_state = (
            "GIL: disabled (nogil)" if not sys._is_gil_enabled() else "GIL: enabled"
        )
        self.title_label = Gtk.Label(
            label=f"{gil_state}  ·  {WORKERS} workers  ·  warming up…",
        )
        header.set_title_widget(self.title_label)
        self.set_titlebar(header)

        self.picture = Gtk.Picture(
            content_fit=Gtk.ContentFit.FILL,
            can_shrink=True,
            hexpand=True,
            vexpand=True,
        )
        self.set_child(self.picture)
        # Watch the window's allocated size and re-render at native res
        # whenever it changes. notify::default-width fires both on user
        # resize and on initial layout.
        self.notify("default-width").connect(self._on_window_size_changed)
        self.notify("default-height").connect(self._on_window_size_changed)

        drag = Gtk.GestureDrag()
        drag.drag_update.connect(self._on_drag_update)
        drag.drag_end.connect(self._on_drag_end)
        self._drag_start_viewport: Viewport | None = None
        self.picture.add_controller(drag)

        scroll = Gtk.EventControllerScroll(
            flags=Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll.scroll.connect(self._on_scroll)
        self.picture.add_controller(scroll)

    # -- input -------------------------------------------------------------

    def _on_drag_update(self, gesture: Gtk.GestureDrag, dx: float, dy: float) -> None:
        if self._drag_start_viewport is None:
            self._drag_start_viewport = self.viewport
        vp = self._drag_start_viewport
        new = Viewport(
            cx=vp.cx - dx * vp.scale,
            cy=vp.cy - dy * vp.scale,
            scale=vp.scale,
            generation=self.viewport.generation + 1,
        )
        self._set_viewport(new)

    def _on_drag_end(self, gesture: Gtk.GestureDrag, dx: float, dy: float) -> None:
        self._drag_start_viewport = None

    def _on_scroll(
        self, controller: Gtk.EventControllerScroll, dx: float, dy: float
    ) -> bool:
        factor = 1.15 if dy > 0 else 1.0 / 1.15
        new = Viewport(
            cx=self.viewport.cx,
            cy=self.viewport.cy,
            scale=self.viewport.scale * factor,
            generation=self.viewport.generation + 1,
        )
        self._set_viewport(new)
        return True

    # -- viewport & tile dispatch -----------------------------------------

    def _set_viewport(self, vp: Viewport) -> None:
        self.viewport = vp
        self.pool.set_generation(vp.generation)
        self._enqueue_all_tiles()

    def _on_window_size_changed(self, *_args: object) -> None:
        global WIDTH, HEIGHT
        # Get current allocated size of the picture (the window size minus
        # the header bar). Falls back to default if not yet realized.
        default_w, default_h = self.get_default_size()
        new_w = default_w
        new_h = default_h - 48
        if new_w < 16 or new_h < 16:
            return
        if new_w == WIDTH and new_h == HEIGHT:
            return
        WIDTH, HEIGHT = new_w, new_h
        self.surface = Surface(WIDTH, HEIGHT)
        # Recenter the viewport scale so what was visible stays visible.
        new_scale = 3.5 / WIDTH
        self.viewport = Viewport(
            cx=self.viewport.cx,
            cy=self.viewport.cy,
            scale=new_scale,
            generation=self.viewport.generation + 1,
        )
        self.pool.set_generation(self.viewport.generation)
        self._enqueue_all_tiles()

    def _enqueue_all_tiles(self) -> None:
        vp = self.viewport
        for ty in range(0, HEIGHT, TILE):
            for tx in range(0, WIDTH, TILE):
                w = min(TILE, WIDTH - tx)
                h = min(TILE, HEIGHT - ty)
                self.pool.submit(Tile(tx=tx, ty=ty, w=w, h=h, viewport=vp))

    # -- main-loop callbacks ----------------------------------------------

    def _drain_and_present(self) -> bool:
        finished = self.pool.drain_finished()
        if not finished:
            return True
        for ft in finished:
            if ft.tile.viewport.generation != self.viewport.generation:
                continue
            self.surface.blit(ft)
        self.picture.set_paintable(self.surface.to_texture())
        return True

    def _update_status(self) -> bool:
        now = time.monotonic()
        count = self.pool.tiles_finished
        self._stat_window.append((now, count))
        cutoff = now - 2.0
        self._stat_window = [(t, c) for (t, c) in self._stat_window if t >= cutoff]
        if len(self._stat_window) >= 2:
            (t0, c0) = self._stat_window[0]
            (t1, c1) = self._stat_window[-1]
            tps = (c1 - c0) / max(t1 - t0, 1e-6)
        else:
            tps = 0.0
        gil_state = "nogil" if not sys._is_gil_enabled() else "GIL on"
        self.title_label.set_label(
            f"{gil_state}  ·  {WORKERS} workers  ·  {tps:6.1f} tiles/s  ·  zoom {1.0 / self.viewport.scale / WIDTH:.2e}"
        )
        return True


# ---------------------------------------------------------------------------
# Application entry point.
# ---------------------------------------------------------------------------


def on_activate(app: Gtk.Application) -> None:
    win = MandelbrotWindow(application=app)
    win.present()


def main(argv: list[str]) -> int:
    app = Gtk.Application(
        application_id="dev.ginext.mandelbrot",
        flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
    )
    app.activate.connect(on_activate)
    try:
        GLibUnix.signal_add(
            GLib.PRIORITY_DEFAULT,
            signal.SIGINT,
            lambda *_a: bool(GLib.idle_add(app.quit)),
        )
    except AttributeError:
        signal.signal(signal.SIGINT, lambda *_: GLib.idle_add(app.quit))
    return app.run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
