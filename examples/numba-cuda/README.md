# Numba CUDA Demo

Small `ginext` + GStreamer demo that renders classic per-pixel effects on an
NVIDIA GPU with `numba.cuda`, copies the RGBA framebuffer back once per frame,
and pushes it through `appsrc`.

This is the GPU sibling to `src/playground/numba_gst_demo.py`:

- `src/playground/numba_gst_demo.py`: CPU kernels, free-threading story
- `examples/numba-cuda/app.py`: CUDA kernels, GPU story

The distinction matters because importing `numba.cuda` currently re-enables the
GIL on our free-threaded Python builds. This example is still useful, but it is
showing GPU parallelism rather than nogil scaling.

## Install

Base example dependencies:

```sh
uv sync --extra apps
```

CUDA-specific Python packages:

```sh
uv pip install "numba-cuda[cu12]"
```

Use `cu13` instead of `cu12` if your toolkit is CUDA 13.x.

You also need a working NVIDIA driver and CUDA-capable GPU. If kernel
compilation fails with a missing `libdevice` error, the CUDA toolkit userspace
pieces are still missing from the environment.

## Run

Open a window with the default sink:

```sh
uv run python examples/numba-cuda/app.py
```

Run headless:

```sh
uv run python examples/numba-cuda/app.py --sink fakesink
```

Run a simple benchmark:

```sh
uv run python examples/numba-cuda/app.py --bench --size 1920x1080
```

The benchmark prints both render+copyback time and kernel-only time so it is
easy to see how much the PCIe/device-to-host transfer costs relative to the
shader-like compute.
