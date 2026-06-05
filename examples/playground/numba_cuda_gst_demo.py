"""GPU demoscene: numba-CUDA per-pixel effects rendered on the GPU and streamed
through a ginext GStreamer pipeline. Sibling to numba_gst_demo.py (CPU + free
threading); this one puts the per-pixel math on the GPU instead.

Why a separate demo from the CPU one
------------------------------------
The CPU demo's whole point was free-threading: @njit(parallel=True) + prange
fanning scanlines across 20 cores with no GIL. CUDA is a *different* parallelism
story and the two don't combine here: importing numba.cuda RE-ENABLES the GIL on
this free-threaded build (its C extension isn't nogil-safe). So:

    numba_gst_demo.py       -> CPU, GIL off, prange over cores  (free threading)
    numba_cuda_gst_demo.py  -> GPU, GIL on,  @cuda.jit 2D grid  (this file)

Same architecture otherwise: a per-pixel kernel fills a flat RGBA framebuffer
that touches zero GObject machinery; only the O(buffers) shell is interpreted.
On the GPU the framebuffer lives in device memory; we copy_to_host once per frame
and hand the bytes to Gst.Buffer.new_wrapped -- cheap now that the ginext array
marshaller has a bulk-memcpy fast path (see marshal/c-array.c).

Environment notes (measured 2026-05-30 on a GTX 1080, CC 6.1)
-----------------------------------------------------------
- numba_cuda references numpy's REMOVED np.trapz, so we shim
  np.trapz = np.trapezoid BEFORE importing numba.cuda or import blows up with
  AttributeError deep in cuda.np.arraymath.
- cuda-bindings warns "built for CUDA 13, driver supports up to 12"; set
  CUDA_PYTHON_DISABLE_MAJOR_VERSION_WARNING=1 to silence. Kernels still run.
- importing numba.cuda re-enables the GIL (RuntimeWarning); harmless here.

Run:
    .venv/bin/python src/playground/numba_cuda_gst_demo.py --bench
    .venv/bin/python src/playground/numba_cuda_gst_demo.py --seconds 20 --size 1920x1080
    add --sink fakesink to run headless.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time

import numpy as np

# numba_cuda still references np.trapz, removed in numpy 2.x. Shim before import.
if not hasattr(np, "trapz"):
    np.trapz = np.trapezoid  # type: ignore[attr-defined]
os.environ.setdefault("CUDA_PYTHON_DISABLE_MAJOR_VERSION_WARNING", "1")

from numba import cuda

import ginext

Gst = ginext.Gst
GstApp = ginext.GstApp  # wires appsrc.push_buffer / end_of_stream
Gst.init(None)


# --------------------------------------------------------------------------
# GPU kernels: one thread per pixel via a 2D grid. cuda.grid(2) gives (y, x).
# --------------------------------------------------------------------------


@cuda.jit
def plasma_gpu(buf, t):
    y, x = cuda.grid(2)
    h, w, _ = buf.shape
    if y >= h or x >= w:
        return
    fx = x * 0.0625
    fy = y * 0.0625
    v = (
        math.sin(fx + t)
        + math.sin(fy + t * 1.3)
        + math.sin((fx + fy + t) * 0.5)
        + math.sin(math.sqrt(fx * fx + fy * fy) + t)
    )
    hue = v * 0.25
    buf[y, x, 0] = np.uint8(int(127.5 + 127.5 * math.cos(6.28318 * hue)) & 0xFF)
    buf[y, x, 1] = np.uint8(
        int(127.5 + 127.5 * math.cos(6.28318 * (hue + 0.33))) & 0xFF
    )
    buf[y, x, 2] = np.uint8(
        int(127.5 + 127.5 * math.cos(6.28318 * (hue + 0.66))) & 0xFF
    )
    buf[y, x, 3] = np.uint8(255)


@cuda.jit
def metaballs_gpu(buf, t):
    y, x = cuda.grid(2)
    h, w, _ = buf.shape
    if y >= h or x >= w:
        return
    b0x = w * (0.5 + 0.35 * math.sin(t))
    b0y = h * (0.5 + 0.35 * math.cos(t * 1.1))
    b1x = w * (0.5 + 0.30 * math.sin(t * 1.7))
    b1y = h * (0.5 + 0.30 * math.cos(t * 0.9))
    b2x = w * (0.5 + 0.40 * math.sin(t * 0.6))
    b2y = h * (0.5 + 0.25 * math.cos(t * 1.5))
    r = (0.04 * w) ** 2
    f = (
        r / ((x - b0x) ** 2 + (y - b0y) ** 2 + 1.0)
        + r / ((x - b1x) ** 2 + (y - b1y) ** 2 + 1.0)
        + r / ((x - b2x) ** 2 + (y - b2y) ** 2 + 1.0)
    )
    if f > 1.0:
        buf[y, x, 0] = np.uint8(255)
        buf[y, x, 1] = np.uint8(min(255, int(120.0 * f)))
        buf[y, x, 2] = np.uint8(min(255, int(40.0 * f)))
    else:
        buf[y, x, 0] = np.uint8(int(80 * f) & 0xFF)
        buf[y, x, 1] = np.uint8(0)
        buf[y, x, 2] = np.uint8(int(40 * f) & 0xFF)
    buf[y, x, 3] = np.uint8(255)


KERNELS = {"plasma": plasma_gpu, "metaballs": metaballs_gpu}
EFFECTS = ["plasma", "metaballs"]
SECS_PER_EFFECT = 5.0


def _grid(w, h, tx=16, ty=16):
    return ((h + ty - 1) // ty, (w + tx - 1) // tx), (ty, tx)


class GpuDemo:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.dev = cuda.device_array((h, w, 4), dtype=np.uint8)  # framebuffer on GPU
        self.host = cuda.pinned_array((h, w, 4), dtype=np.uint8)  # fast copy-back
        self.blocks, self.threads = _grid(w, h)
        self.render_ms = 0.0

    def warmup(self):
        for k in KERNELS.values():
            k[self.blocks, self.threads](self.dev, 0.0)
        cuda.synchronize()

    def render(self, t):
        name = EFFECTS[int(t / SECS_PER_EFFECT) % len(EFFECTS)]
        r0 = time.perf_counter()
        KERNELS[name][self.blocks, self.threads](self.dev, t)
        self.dev.copy_to_host(self.host)
        cuda.synchronize()
        dt = (time.perf_counter() - r0) * 1000.0
        self.render_ms = dt if self.render_ms == 0 else 0.9 * self.render_ms + 0.1 * dt
        return name


def make_buffer(host_frame):
    # host_frame is contiguous uint8 -> the ginext array fast path memcpys it.
    return Gst.Buffer.new_wrapped(memoryview(host_frame).cast("B"))


def bench(w, h):
    demo = GpuDemo(w, h)
    demo.warmup()
    REPS = 60
    print(f"[bench] GPU render+copyback @ {w}x{h}, {REPS} reps/effect:")
    for name in EFFECTS:
        t0 = time.perf_counter()
        for i in range(REPS):
            KERNELS[name][demo.blocks, demo.threads](demo.dev, i * 0.05)
            demo.dev.copy_to_host(demo.host)
        cuda.synchronize()
        ms = (time.perf_counter() - t0) / REPS * 1000.0
        print(f"[bench] {name:10s} {ms:6.2f} ms/frame  -> {1000 / ms:6.1f} fps")
    # kernel-only (no copyback) to show raw compute vs the PCIe transfer cost
    for name in EFFECTS:
        t0 = time.perf_counter()
        for i in range(REPS):
            KERNELS[name][demo.blocks, demo.threads](demo.dev, i * 0.05)
        cuda.synchronize()
        ms = (time.perf_counter() - t0) / REPS * 1000.0
        print(f"[bench] {name:10s} {ms:6.2f} ms/frame  (kernel only, no copyback)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--sink", default="ximagesink")
    ap.add_argument("--bench", action="store_true")
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split("x"))

    if not cuda.is_available():
        print(
            "[demo] no CUDA device; this demo needs a GPU. "
            "Use numba_gst_demo.py for the CPU/free-threading version."
        )
        os._exit(1)

    dev = cuda.get_current_device()
    print(
        f"[demo] GPU: {dev.name.decode() if isinstance(dev.name, bytes) else dev.name}  "
        f"CC {dev.compute_capability}  {w}x{h}@{args.fps}  sink={args.sink}"
    )

    demo = GpuDemo(w, h)
    print("[demo] warming up CUDA kernels...")
    tw = time.perf_counter()
    demo.warmup()
    print(f"[demo] warmup done in {time.perf_counter() - tw:.2f}s")

    if args.bench:
        bench(w, h)
        sys.stdout.flush()
        os._exit(0)

    pipe = Gst.parse_launch(
        f"appsrc name=src is-live=true format=time do-timestamp=true "
        f"caps=video/x-raw,format=RGBA,width={w},height={h},framerate={args.fps}/1 "
        f"! queue max-size-buffers=3 leaky=downstream ! videoconvert ! {args.sink} sync=false"
    )
    src = pipe.get_by_name("src")
    pipe.set_state(Gst.State.PLAYING)

    frame_dur = 1.0 / args.fps
    start = time.perf_counter()
    last = start
    pushed = 0
    try:
        while True:
            now = time.perf_counter()
            t = now - start
            if t >= args.seconds:
                break
            name = demo.render(t)
            if int(src.push_buffer(make_buffer(demo.host))) != 0:
                break
            pushed += 1
            if now - last >= 1.0:
                print(
                    f"[demo] {name:10s} gpu={demo.render_ms:5.2f}ms/frame  "
                    f"{pushed / (now - start):5.1f} fps  frames={pushed}"
                )
                last = now
            sleep = frame_dur - (time.perf_counter() - now)
            if sleep > 0:
                time.sleep(sleep)
    finally:
        src.end_of_stream()
        time.sleep(0.1)
        pipe.set_state(Gst.State.NULL)

    print(f"[demo] done: {pushed} frames in {time.perf_counter() - start:.1f}s")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
