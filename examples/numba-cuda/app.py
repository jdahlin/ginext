#!/usr/bin/env python3
"""GPU demoscene rendered with numba-cuda and streamed through ginext Gst.

This is the GPU sibling to ``src/playground/numba_gst_demo.py``:

- CPU demo: free-threaded Python, ``@njit(parallel=True)``, work spread across cores
- This demo: CUDA kernels on the GPU, Python shell stays thin

Important caveat: importing ``numba.cuda`` currently re-enables the GIL on our
free-threaded Python build, so this is a GPU parallelism showcase, not a nogil
showcase.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time

import numpy as np

import ginext

Gst = ginext.Gst
GstApp = ginext.GstApp
Gst.init(None)

cuda = None


def load_cuda():
    global cuda
    if cuda is not None:
        return cuda

    if not hasattr(np, "trapz"):
        np.trapz = np.trapezoid  # type: ignore[attr-defined]
    os.environ.setdefault("CUDA_PYTHON_DISABLE_MAJOR_VERSION_WARNING", "1")

    try:
        from numba import cuda as numba_cuda
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "This example needs Numba CUDA userspace packages. Install them with:\n"
            "  uv sync --extra apps\n"
            "  uv pip install 'numba-cuda[cu12]'\n"
            "Adjust [cu12] to [cu13] if your CUDA toolkit is 13.x."
        ) from exc

    cuda = numba_cuda
    return cuda


def parse_size(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        return int(width_text), int(height_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid size {value!r}; expected WIDTHxHEIGHT"
        ) from exc


def _grid(
    width: int, height: int, tx: int = 16, ty: int = 16
) -> tuple[tuple[int, int], tuple[int, int]]:
    return ((height + ty - 1) // ty, (width + tx - 1) // tx), (ty, tx)


def make_kernels():
    cuda_mod = load_cuda()

    @cuda_mod.jit
    def plasma_gpu(buf, t):
        y, x = cuda_mod.grid(2)
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

    @cuda_mod.jit
    def metaballs_gpu(buf, t):
        y, x = cuda_mod.grid(2)
        h, w, _ = buf.shape
        if y >= h or x >= w:
            return
        b0x = w * (0.5 + 0.35 * math.sin(t))
        b0y = h * (0.5 + 0.35 * math.cos(t * 1.1))
        b1x = w * (0.5 + 0.30 * math.sin(t * 1.7))
        b1y = h * (0.5 + 0.30 * math.cos(t * 0.9))
        b2x = w * (0.5 + 0.40 * math.sin(t * 0.6))
        b2y = h * (0.5 + 0.25 * math.cos(t * 1.5))
        radius = (0.04 * w) ** 2
        f = (
            radius / ((x - b0x) ** 2 + (y - b0y) ** 2 + 1.0)
            + radius / ((x - b1x) ** 2 + (y - b1y) ** 2 + 1.0)
            + radius / ((x - b2x) ** 2 + (y - b2y) ** 2 + 1.0)
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

    return {"plasma": plasma_gpu, "metaballs": metaballs_gpu}


EFFECTS = ["plasma", "metaballs"]
SECS_PER_EFFECT = 5.0


class GpuDemo:
    def __init__(self, width: int, height: int, kernels):
        cuda_mod = load_cuda()
        self.width = width
        self.height = height
        self.kernels = kernels
        self.dev = cuda_mod.device_array((height, width, 4), dtype=np.uint8)
        self.host = cuda_mod.pinned_array((height, width, 4), dtype=np.uint8)
        self.blocks, self.threads = _grid(width, height)
        self.render_ms = 0.0

    def warmup(self) -> None:
        cuda_mod = load_cuda()
        for kernel in self.kernels.values():
            kernel[self.blocks, self.threads](self.dev, 0.0)
        cuda_mod.synchronize()

    def render(self, t: float) -> str:
        cuda_mod = load_cuda()
        name = EFFECTS[int(t / SECS_PER_EFFECT) % len(EFFECTS)]
        t0 = time.perf_counter()
        self.kernels[name][self.blocks, self.threads](self.dev, t)
        self.dev.copy_to_host(self.host)
        cuda_mod.synchronize()
        dt = (time.perf_counter() - t0) * 1000.0
        self.render_ms = dt if self.render_ms == 0 else 0.9 * self.render_ms + 0.1 * dt
        return name


def make_buffer(host_frame: np.ndarray):
    return Gst.Buffer.new_wrapped(memoryview(host_frame).cast("B"))


def bench(width: int, height: int, kernels) -> None:
    cuda_mod = load_cuda()
    demo = GpuDemo(width, height, kernels)
    demo.warmup()
    reps = 60
    print(f"[bench] GPU render+copyback @ {width}x{height}, {reps} reps/effect:")
    for name in EFFECTS:
        t0 = time.perf_counter()
        for i in range(reps):
            kernels[name][demo.blocks, demo.threads](demo.dev, i * 0.05)
            demo.dev.copy_to_host(demo.host)
        cuda_mod.synchronize()
        ms = (time.perf_counter() - t0) / reps * 1000.0
        print(f"[bench] {name:10s} {ms:6.2f} ms/frame  -> {1000 / ms:6.1f} fps")
    for name in EFFECTS:
        t0 = time.perf_counter()
        for i in range(reps):
            kernels[name][demo.blocks, demo.threads](demo.dev, i * 0.05)
        cuda_mod.synchronize()
        ms = (time.perf_counter() - t0) / reps * 1000.0
        print(f"[bench] {name:10s} {ms:6.2f} ms/frame  (kernel only, no copyback)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=20.0)
    parser.add_argument("--size", type=parse_size, default=(1280, 720))
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--sink", default="ximagesink")
    parser.add_argument("--bench", action="store_true")
    args = parser.parse_args()
    width, height = args.size

    cuda_mod = load_cuda()
    kernels = make_kernels()

    if not cuda_mod.is_available():
        raise SystemExit(
            "No CUDA device available. This example needs an NVIDIA GPU.\n"
            "Use src/playground/numba_gst_demo.py for the CPU/free-threading variant."
        )

    device = cuda_mod.get_current_device()
    device_name = (
        device.name.decode() if isinstance(device.name, bytes) else device.name
    )
    is_gil_enabled = sys.__dict__.get("_is_gil_enabled")
    gil = "off" if callable(is_gil_enabled) and not is_gil_enabled() else "on"
    print(
        f"[demo] GPU={device_name} CC={device.compute_capability} "
        f"size={width}x{height} fps={args.fps} sink={args.sink} GIL={gil}"
    )

    demo = GpuDemo(width, height, kernels)
    print("[demo] warming up CUDA kernels...")
    t0 = time.perf_counter()
    try:
        demo.warmup()
    except RuntimeError as exc:
        message = str(exc)
        if "Missing libdevice file" in message:
            raise SystemExit(
                "CUDA kernel compilation could not find libdevice.\n"
                "Install the matching toolkit userspace packages, for example:\n"
                "  uv pip install 'numba-cuda[cu12]'\n"
                "or use a system/Conda CUDA toolkit that provides libdevice."
            ) from exc
        raise
    print(f"[demo] warmup done in {time.perf_counter() - t0:.2f}s")

    if args.bench:
        bench(width, height, kernels)
        return

    pipeline = Gst.parse_launch(
        f"appsrc name=src is-live=true format=time do-timestamp=true "
        f"caps=video/x-raw,format=RGBA,width={width},height={height},framerate={args.fps}/1 "
        f"! queue max-size-buffers=3 leaky=downstream ! videoconvert ! {args.sink} sync=false"
    )
    src = pipeline.get_by_name("src")
    pipeline.set_state(Gst.State.PLAYING)

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
        pipeline.set_state(Gst.State.NULL)

    print(f"[demo] done: {pushed} frames in {time.perf_counter() - start:.1f}s")


if __name__ == "__main__":
    main()
