"""C64/demoscene megademo: numba-JIT per-pixel effects, free-threaded across
all cores, rendered live through a GStreamer pipeline via ginext.

Why this is a good showcase
---------------------------
Every effect here is pure arithmetic over a flat RGBA framebuffer -- exactly the
"Python object outside, flat numeric memory inside" boundary numba wants. The
GObject side (appsrc, buffer alloc, pipeline) is touched once per frame (~60/s);
the per-pixel math runs W*H*60 times/s and touches zero GObject machinery. So we
JIT only the kernels and fan their scanlines across cores with prange -- on
free-threaded 3.14 there's no GIL to serialize them.

Effects cycle: plasma -> tunnel -> rotozoomer -> metaballs -> fire.

Pipeline:  appsrc (we push rendered RGBA) ! videoconvert ! autovideosink
Run:       .venv/bin/python src/playground/numba_gst_demo.py [--seconds N] [--size WxH]
           add --sink fakesink   to run headless (no window), still renders+times
"""

from __future__ import annotations

import argparse
import math
import sys
import time

import numpy as np
from numba import njit, prange

import ginext

Gst = ginext.Gst
GLib = ginext.GLib
# Importing GstApp wires appsrc's push_buffer()/end_of_stream() methods onto the
# wrapped element; without it appsrc is just a plain Gst.Element and those calls
# raise AttributeError.
GstApp = ginext.GstApp
Gst.init(None)


# --------------------------------------------------------------------------
# Kernels -- the only JIT-compiled, the only hot, the only parallel code.
# Each writes an (H, W, 4) uint8 RGBA frame. parallel=True + prange over rows
# spreads the frame across cores; on 3.14t these threads run truly concurrently.
# --------------------------------------------------------------------------


@njit(cache=True, fastmath=True)
def _hsv_r(h):  # tiny helper: hue (0..1) -> R of a rainbow, no branches in hot path
    return 0.5 + 0.5 * math.cos(6.28318 * (h + 0.0))


@njit(cache=True, parallel=True, fastmath=True)
def plasma(buf, t):
    H, W, _ = buf.shape
    for y in prange(H):
        fy = y * 0.0625
        for x in range(W):
            fx = x * 0.0625
            v = (
                math.sin(fx + t)
                + math.sin(fy + t * 1.3)
                + math.sin((fx + fy + t) * 0.5)
                + math.sin(math.sqrt(fx * fx + fy * fy) + t)
            )
            h = v * 0.25
            buf[y, x, 0] = int(127.5 + 127.5 * math.cos(6.28318 * h))
            buf[y, x, 1] = int(127.5 + 127.5 * math.cos(6.28318 * (h + 0.33)))
            buf[y, x, 2] = int(127.5 + 127.5 * math.cos(6.28318 * (h + 0.66)))
            buf[y, x, 3] = 255


@njit(cache=True, parallel=True, fastmath=True)
def tunnel(buf, t):
    H, W, _ = buf.shape
    cx, cy = W * 0.5, H * 0.5
    for y in prange(H):
        dy = y - cy
        for x in range(W):
            dx = x - cx
            dist = math.sqrt(dx * dx + dy * dy) + 1e-3
            ang = math.atan2(dy, dx)
            u = 0.5 + 0.5 * math.sin(8.0 / dist * 40.0 + t * 2.0)
            v = 0.5 + 0.5 * math.sin(ang * 5.0 + t)
            shade = u * v
            buf[y, x, 0] = int(255 * shade)
            buf[y, x, 1] = int(180 * shade * v)
            buf[y, x, 2] = int(255 * (1.0 - shade))
            buf[y, x, 3] = 255


@njit(cache=True, parallel=True, fastmath=True)
def rotozoom(buf, t):
    H, W, _ = buf.shape
    cx, cy = W * 0.5, H * 0.5
    zoom = 1.5 + math.sin(t) * 0.8
    ca, sa = math.cos(t * 0.7) * zoom, math.sin(t * 0.7) * zoom
    for y in prange(H):
        dy = y - cy
        for x in range(W):
            dx = x - cx
            u = int(dx * ca - dy * sa) & 63  # sample a 64x64 checker texture
            v = int(dx * sa + dy * ca) & 63
            on = ((u ^ v) >> 5) & 1  # xor-checker pattern
            r = 60 + 195 * on
            buf[y, x, 0] = r
            buf[y, x, 1] = int(r * (0.5 + 0.5 * math.sin(t)))
            buf[y, x, 2] = 255 - r
            buf[y, x, 3] = 255


@njit(cache=True, parallel=True, fastmath=True)
def metaballs(buf, t):
    H, W, _ = buf.shape
    # 4 moving blobs; per pixel sums 1/dist^2 -- the heaviest kernel here.
    b0x, b0y = W * (0.5 + 0.35 * math.sin(t)), H * (0.5 + 0.35 * math.cos(t * 1.1))
    b1x, b1y = (
        W * (0.5 + 0.30 * math.sin(t * 1.7)),
        H * (0.5 + 0.30 * math.cos(t * 0.9)),
    )
    b2x, b2y = (
        W * (0.5 + 0.40 * math.sin(t * 0.6)),
        H * (0.5 + 0.25 * math.cos(t * 1.5)),
    )
    b3x, b3y = (
        W * (0.5 + 0.25 * math.sin(t * 2.1)),
        H * (0.5 + 0.40 * math.cos(t * 0.7)),
    )
    R = (0.04 * W) ** 2
    for y in prange(H):
        for x in range(W):
            f = (
                R / ((x - b0x) ** 2 + (y - b0y) ** 2 + 1.0)
                + R / ((x - b1x) ** 2 + (y - b1y) ** 2 + 1.0)
                + R / ((x - b2x) ** 2 + (y - b2y) ** 2 + 1.0)
                + R / ((x - b3x) ** 2 + (y - b3y) ** 2 + 1.0)
            )
            if f > 1.0:
                buf[y, x, 0] = 255
                buf[y, x, 1] = int(min(255.0, 120.0 * f))
                buf[y, x, 2] = int(min(255.0, 40.0 * f))
            else:
                c = int(80 * f)
                buf[y, x, 0] = c
                buf[y, x, 1] = 0
                buf[y, x, 2] = int(40 * f)
            buf[y, x, 3] = 255


@njit(cache=True, parallel=True, fastmath=True)
def _fire_palette(buf, heat):
    H, W, _ = buf.shape
    for y in prange(H):
        for x in range(W):
            h = heat[y, x]
            buf[y, x, 0] = min(255, h * 3)
            buf[y, x, 1] = 0 if h < 85 else min(255, (h - 85) * 3)
            buf[y, x, 2] = 0 if h < 170 else min(255, (h - 170) * 3)
            buf[y, x, 3] = 255


@njit(cache=True, parallel=True)
def _fire_step(heat, seed):
    # Classic Doom fire: hot random bottom row, propagate upward with decay.
    # Row y depends on rows below it, so y MUST stay sequential -- we parallelize
    # x within each row instead. (Putting prange on y would be a data race on
    # free-threaded Python: threads would read neighbor rows mid-write.)
    H, W = heat.shape
    for x in prange(W):
        heat[H - 1, x] = (seed * (x * 2654435761 + 1) >> 8) & 255
    for y in range(H - 2, -1, -1):
        for x in prange(W):
            below = heat[y + 1, x]
            left = heat[y + 1, x - 1] if x > 0 else below
            right = heat[y + 1, x + 1] if x < W - 1 else below
            avg = (below + left + right + heat[min(y + 2, H - 1), x]) >> 2
            heat[y, x] = avg - (avg > 2)


# --------------------------------------------------------------------------
# Effect scheduler
# --------------------------------------------------------------------------

EFFECTS = ["plasma", "tunnel", "rotozoom", "metaballs", "fire"]
SECS_PER_EFFECT = 4.0


class Demo:
    def __init__(self, w, h, fps):
        self.w, self.h, self.fps = w, h, fps
        self.frame = np.zeros((h, w, 4), dtype=np.uint8)
        self.heat = np.zeros((h, w), dtype=np.int32)
        self.frame_no = 0
        self.t0 = time.perf_counter()
        self.render_ms_ema = 0.0

    def warmup(self):
        # Compile every kernel off the streaming path so no frame stalls.
        t = 0.0
        plasma(self.frame, t)
        tunnel(self.frame, t)
        rotozoom(self.frame, t)
        metaballs(self.frame, t)
        _fire_step(self.heat, 1)
        _fire_palette(self.frame, self.heat.astype(np.uint8))

    def render(self, t):
        idx = int(t / SECS_PER_EFFECT) % len(EFFECTS)
        name = EFFECTS[idx]
        r0 = time.perf_counter()
        if name == "plasma":
            plasma(self.frame, t)
        elif name == "tunnel":
            tunnel(self.frame, t)
        elif name == "rotozoom":
            rotozoom(self.frame, t)
        elif name == "metaballs":
            metaballs(self.frame, t)
        else:
            _fire_step(self.heat, (self.frame_no * 97 + 13) & 0x7FFFFFFF)
            _fire_palette(self.frame, self.heat.astype(np.uint8))
        dt = (time.perf_counter() - r0) * 1000.0
        self.render_ms_ema = (
            dt if self.frame_no == 0 else 0.9 * self.render_ms_ema + 0.1 * dt
        )
        return name


def bench(demo, ncores):
    # Time each effect with numba pinned to 1 thread, then to all cores. The
    # ratio is the free-threading speedup -- on stock CPython the GIL would cap
    # this near 1x; here prange spreads scanlines across real cores.
    import numba

    REPS = 30
    kernels = [
        ("plasma", lambda t: plasma(demo.frame, t)),
        ("tunnel", lambda t: tunnel(demo.frame, t)),
        ("rotozoom", lambda t: rotozoom(demo.frame, t)),
        ("metaballs", lambda t: metaballs(demo.frame, t)),
    ]

    def time_at(nthreads, fn):
        numba.set_num_threads(nthreads)
        fn(0.0)  # re-specialize for this thread count
        t0 = time.perf_counter()
        for i in range(REPS):
            fn(i * 0.05)
        return (time.perf_counter() - t0) / REPS * 1000.0

    print(f"[bench] {demo.w}x{demo.h}, {REPS} reps/effect, 1 thread vs {ncores} cores")
    print(
        f"[bench] {'effect':10s} {'1-thread':>10s} {'all-cores':>10s} {'speedup':>8s}"
    )
    for name, fn in kernels:
        t1 = time_at(1, fn)
        tn = time_at(ncores, fn)
        print(f"[bench] {name:10s} {t1:8.2f}ms {tn:8.2f}ms {t1 / tn:6.1f}x")


def profile_stages(demo, src, n):
    # Break each frame into its stages so we can see where the time actually
    # goes -- render vs the bytes() copy vs alloc+fill vs push_buffer.
    import statistics as st

    acc = {"render": [], "tobytes": [], "alloc+fill": [], "push": [], "total": []}
    for i in range(n):
        f0 = time.perf_counter()
        demo.render(0.1 + i * 0.01)
        f1 = time.perf_counter()
        raw = demo.frame.tobytes()
        f2 = time.perf_counter()
        buf = Gst.Buffer.new_allocate(None, len(raw), None)
        buf.fill(0, raw)
        f3 = time.perf_counter()
        src.push_buffer(buf)
        f4 = time.perf_counter()
        acc["render"].append((f1 - f0) * 1000)
        acc["tobytes"].append((f2 - f1) * 1000)
        acc["alloc+fill"].append((f3 - f2) * 1000)
        acc["push"].append((f4 - f3) * 1000)
        acc["total"].append((f4 - f0) * 1000)
    print(f"[profile] {n} frames @ {demo.w}x{demo.h}, plasma; median ms/frame:")
    for k in ("render", "tobytes", "alloc+fill", "push", "total"):
        v = acc[k]
        print(
            f"[profile] {k:8s} median={st.median(v):7.2f}  "
            f"max={max(v):7.2f}  mean={sum(v) / len(v):7.2f}"
        )
    tot = st.median(acc["total"])
    if tot > 0:
        print(f"[profile] implied ceiling: {1000 / tot:.1f} fps")


def make_buffer(frame):
    # Pass the numpy frame straight to new_wrapped -- no tobytes(), no extra
    # Python copy. ginext's array IN-arg marshaller (marshal/c-array.c) now has
    # a buffer-protocol memcpy fast path, so a contiguous uint8 ndarray is bulk
    # -copied into the GstBuffer at ~18 GB/s (~0.2ms for a 720p frame). Before
    # that fix this path was a per-element Python-int loop at ~20 MB/s (~190ms),
    # which was the entire bottleneck -- not the kernel, not the sink.
    return Gst.Buffer.new_wrapped(memoryview(frame).cast("B"))


def build_pipeline(w, h, fps, sink):
    # The display sink is the real bottleneck, not the kernel: profiling showed
    # push->autovideosink = 194ms/frame (autovideosink resolves to a software-GL
    # path here), vs ximagesink = 0.9ms/frame. So default to ximagesink and put
    # a leaky queue in front so the sink runs on its OWN thread -- push_buffer
    # returns immediately and rendering overlaps with display instead of
    # blocking on it. leaky=downstream drops stale frames to keep latency low.
    pipe = Gst.parse_launch(
        f"appsrc name=src is-live=true format=time do-timestamp=true "
        f"caps=video/x-raw,format=RGBA,width={w},height={h},framerate={fps}/1 "
        f"! queue max-size-buffers=3 leaky=downstream "
        f"! videoconvert ! {sink} name=sink sync=false"
    )
    return pipe, pipe.get_by_name("src")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--size", default="640x480")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--sink", default="ximagesink")
    ap.add_argument(
        "--bench",
        action="store_true",
        help="time each effect at 1 thread vs all cores, then exit",
    )
    ap.add_argument(
        "--profile",
        type=int,
        default=0,
        metavar="N",
        help="push N frames timing each stage, then exit",
    )
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split("x"))

    import os

    nthreads = len(os.sched_getaffinity(0))
    is_gil_enabled = sys.__dict__.get("_is_gil_enabled")
    gil = "off" if callable(is_gil_enabled) and not is_gil_enabled() else "on"
    print(f"[demo] {w}x{h}@{args.fps}  cores={nthreads}  GIL={gil}  sink={args.sink}")

    demo = Demo(w, h, args.fps)
    print("[demo] warming up JIT kernels (compiling off the streaming thread)...")
    tw = time.perf_counter()
    demo.warmup()
    print(f"[demo] warmup done in {time.perf_counter() - tw:.2f}s")

    if args.bench:
        bench(demo, nthreads)
        sys.stdout.flush()
        os._exit(0)

    pipe, src = build_pipeline(w, h, args.fps, args.sink)
    pipe.set_state(Gst.State.PLAYING)

    if args.profile:
        profile_stages(demo, src, args.profile)
        src.end_of_stream()
        time.sleep(0.1)
        pipe.set_state(Gst.State.NULL)
        sys.stdout.flush()
        os._exit(0)

    frame_dur = 1.0 / args.fps
    start = time.perf_counter()
    last_report = start
    pushed = 0
    try:
        while True:
            now = time.perf_counter()
            t = now - start
            if t >= args.seconds:
                break
            name = demo.render(t)
            ret = src.push_buffer(make_buffer(demo.frame))  # see make_buffer
            if int(ret) != 0:  # not GST_FLOW_OK
                print(f"[demo] push returned {ret}, stopping")
                break
            demo.frame_no += 1
            pushed += 1
            if now - last_report >= 1.0:
                fps_actual = pushed / (now - start)
                print(
                    f"[demo] {name:9s}  render={demo.render_ms_ema:5.1f}ms/frame  "
                    f"throughput={fps_actual:4.1f} fps  frames={pushed}"
                )
                last_report = now
            sleep_left = frame_dur - (time.perf_counter() - now)
            if sleep_left > 0:
                time.sleep(sleep_left)
    finally:
        src.end_of_stream()
        time.sleep(0.1)
        pipe.set_state(Gst.State.NULL)

    print(f"[demo] done: {pushed} frames in {time.perf_counter() - start:.1f}s")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)  # skip crashy free-threaded GStreamer shutdown finalizers


if __name__ == "__main__":
    main()
