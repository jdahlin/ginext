# Media Effects

Small GTK/GStreamer demo that pulls webcam, video-file, or test-source frames
into NumPy and renders live effects back into a `Gtk.Picture`.

By default the GStreamer pipeline does not force a resolution or framerate;
it lets the source negotiate its native caps and processes frames as quickly
as `appsink` delivers them. Use `--width` and `--height` only when you want
to force a smaller capture size.

The interesting boundary is intentionally kept in `gst_buffer_to_numpy()`
inside `app.py`: today it uses `Gst.Buffer.extract_dup()` and NumPy wraps
the copied bytes. Once goi exposes mapped buffer memory as a safe Python
buffer, that helper can return a zero-copy NumPy view without changing the
effect code.

The NumPy path pulls and processes frames on a worker thread so GTK only
presents already-packed frames. The header shows FPS plus copy/effect/pack
timings for the newest frame.

Run with a webcam:

```sh
uv sync --extra apps
uv run python examples/webcam-effects/app.py
```

Run with a local video file:

```sh
uv sync --extra apps
uv run python examples/webcam-effects/app.py --file /path/to/video.mp4 --fullscreen
```

You can also start the app first and use the Open button to pick a video file.

Compare against native GStreamer display, bypassing NumPy and `appsink`:

```sh
uv run python examples/webcam-effects/app.py --native --file /path/to/video.mp4 --fullscreen
```

Run without a webcam, using GStreamer's synthetic test source:

```sh
uv sync --extra apps
uv run python examples/webcam-effects/app.py --test-source
```

The first version deliberately avoids Numba. The effects are vectorized
NumPy only, which keeps the demo easy to run while still showing why direct
`Gst.Buffer` array access is useful.
