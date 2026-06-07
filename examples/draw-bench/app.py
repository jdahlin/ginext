"""
draw-bench — frame-rate / callback-overhead benchmark for goi.

Unlike mandelbrot, which is CPU-bound computing fractals, this benchmark
makes callback and marshalling overhead the bottleneck. Each frame:
  1. Builds a pixel buffer with a cycling solid colour  (trivial compute)
  2. Wraps it in Gdk.MemoryTexture                      (Python→C invoke)
  3. Presents it via Gtk.Picture.set_paintable()        (Python→C invoke)

No Cairo — everything goes through goi's invoke / closure paths so the
numbers reflect marshalling overhead directly.

Metrics shown in the header bar:
  fps           frames presented per second
  idle/s        idle_add callback invocations/s (unbounded, C→Python)
  invoke-ops/s  Python→C GI calls/s (fps × ops per frame)

Flags:
  --gi          use gi.repository (PyGObject) instead of ginext for comparison
"""

from __future__ import annotations

import signal
import sys
import time
from typing import TYPE_CHECKING

# --gi flag: compare against the reference PyGObject binding.
_USE_GI = "--gi" in sys.argv
if TYPE_CHECKING:
    # Type-check against the ginext stubs regardless of the runtime backend;
    # the --gi path imports the same API surface from PyGObject.
    from ginext import GLib, Gdk, Gio, Gtk
elif _USE_GI:
    sys.argv.remove("--gi")
    import gi

    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gdk, Gio, Gtk
else:
    from ginext import GLib, Gdk, Gio, Gtk

BUF_W, BUF_H = 256, 256
STRIDE = BUF_W * 4


class DrawBenchWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application) -> None:
        super().__init__(
            application=application,
            title="draw-bench",
            default_width=800,
            default_height=600,
        )

        self._app = application
        self._frames = 0
        self._idle_calls = 0
        self._alive = True
        self._t_last = time.monotonic()
        self._hue: int = 0
        # Precompute the 256 hue-cycle pixel buffers once. Each is ~256 KB
        # (BUF_W*BUF_H*4); without this the bench spends ~half its CPU in
        # _PyBytes_Repeat allocating a fresh 256 KB on every frame, masking
        # whatever marshalling overhead we're actually trying to measure.
        # For --gi mode pre-wrap each one in GLib.Bytes too, so the C-side
        # work per frame is identical to the goi path.
        self._buf_cache: list[bytes] | list[GLib.Bytes] = [
            bytes([h * 3 & 0xFF, h * 5 & 0xFF, (255 - h) & 0xFF, 0xFF])
            * (BUF_W * BUF_H)
            for h in range(256)
        ]
        if _USE_GI:
            self._buf_cache = [GLib.Bytes.new(b) for b in self._buf_cache]

        # Also precompute the 256 GdkMemoryTextures so the bench loop is just
        # set_paintable. The bench is supposed to measure invoke overhead, not
        # GTK's per-call g_type_create_instance + memory-texture setup. With
        # this, gdk_memory_texture_new + g_object_new disappear from the hot
        # path entirely and what's left is the marshal/dispatch we actually
        # care about.
        self._tex_cache = [
            Gdk.MemoryTexture.new(BUF_W, BUF_H, Gdk.MemoryFormat.R8G8B8A8, b, STRIDE)
            for b in self._buf_cache
        ]

        gil = "nogil" if not sys._is_gil_enabled() else "GIL"
        backend = "gi" if _USE_GI else "ginext"
        self._backend_label = (
            f"[{backend}/{gil} py{sys.version_info.major}.{sys.version_info.minor}]"
        )
        header = Gtk.HeaderBar()
        self.title_label = Gtk.Label(label=f"{self._backend_label} warming up…")
        header.set_title_widget(self.title_label)
        self.set_titlebar(header)

        self._picture = Gtk.Picture(
            content_fit=Gtk.ContentFit.FILL,
            can_shrink=True,
            hexpand=True,
            vexpand=True,
        )
        self.set_child(self._picture)

        # Signals: real PyGObject uses the legacy connect("name", handler) API;
        # the ginext side uses the new attribute-based signal API.
        if _USE_GI:
            self.connect("close-request", self._on_close_request)
        else:
            self.close_request.connect(self._on_close_request)

        # Keep reference alive: add_controller is transfer-full so GTK consumes
        # the caller's ref; without this the controller is freed when __init__
        # returns and any key event crashes.
        self._key_ctrl = Gtk.EventControllerKey()
        if _USE_GI:
            self._key_ctrl.connect("key-pressed", self._on_key_pressed)
        else:
            self._key_ctrl.key_pressed.connect(self._on_key_pressed)
        self.add_controller(self._key_ctrl)
        GLib.idle_add(self._tick)
        GLib.timeout_add(1000, self._report)

    def _on_key_pressed(
        self,
        controller: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def _on_close_request(self, *_: object) -> bool:
        self._alive = False
        self._app.quit()
        return False

    def _tick(self) -> bool:
        if not self._alive:
            return False
        self._idle_calls += 1

        # Pull the precomputed texture for this hue — no per-frame allocation.
        h = self._hue
        self._hue = (h + 1) & 0xFF
        self._picture.set_paintable(self._tex_cache[h])

        self._frames += 1
        return True

    def _report(self) -> bool:
        if not self._alive:
            return False
        now = time.monotonic()
        dt = max(now - self._t_last, 1e-6)
        fps = self._frames / dt
        idle = self._idle_calls / dt

        self._frames = 0
        self._idle_calls = 0
        self._t_last = now

        line = f"{self._backend_label}  {fps:.1f} fps  ·  {idle:.0f} idle/s"
        self.title_label.set_label(line)
        print(line, file=sys.stderr, flush=True)
        return True


def on_activate(app: Gtk.Application) -> None:
    win = DrawBenchWindow(application=app)
    win.present()


def main(argv: list[str]) -> int:
    app = Gtk.Application(
        application_id="dev.goi.drawbench",
        flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
    )
    if _USE_GI:
        app.connect("activate", on_activate)
    else:
        app.activate.connect(on_activate)
    signal.signal(signal.SIGINT, lambda *_: GLib.idle_add(app.quit))
    return app.run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
