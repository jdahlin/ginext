#!/usr/bin/env python3
"""Live NumPy media effects for goi.

This is a deliberately small demo app:

  webcam/video/test source -> GStreamer RGBA buffer -> NumPy effect -> Gtk.Picture

Run:
    uv sync --extra apps
    uv run python examples/webcam-effects/app.py

Use --file for video files, or --test-source if no webcam is available.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

try:
    import numpy as np
except ModuleNotFoundError as exc:
    raise SystemExit(
        "This demo needs NumPy. Install it with: uv sync --extra apps"
    ) from exc

import goi

goi.require_version("Gdk", "4.0")
goi.require_version("Gio", "2.0")
goi.require_version("Gst", "1.0")
goi.require_version("Gtk", "4.0")

from goi.repository import Gdk, Gio, GLib, Gst, Gtk  # noqa: E402


HISTORY_FRAMES = 36
GLIB_PRIORITY_DEFAULT_IDLE = 200


@dataclass(frozen=True)
class Frame:
    pixels: np.ndarray
    width: int
    height: int
    stride: int


@dataclass(frozen=True)
class ProcessedFrame:
    data: bytes
    width: int
    height: int
    stride: int
    copy_ms: float
    effect_ms: float
    pack_ms: float


def gst_buffer_to_numpy(buffer: Gst.Buffer, width: int, height: int) -> Frame:
    """Return an RGBA NumPy view for a Gst.Buffer.

    The current goi Gst.Buffer.map overlay exposes a bytes copy. Using
    extract_dup() directly keeps the demo from accumulating mapped buffers,
    and this helper is the single place to replace once goi has a true mapped
    memoryview API.
    """
    expected_size = width * height * 4
    data = buffer.extract_dup(0, min(buffer.get_size(), expected_size))
    if len(data) < expected_size:
        raise ValueError(f"short video buffer: {len(data)} < {expected_size}")
    pixels = np.frombuffer(data, dtype=np.uint8, count=expected_size)
    return Frame(pixels.reshape((height, width, 4)), width, height, width * 4)


def processed_frame_to_texture(frame: ProcessedFrame) -> Gdk.Texture:
    return Gdk.MemoryTexture.new(
        frame.width,
        frame.height,
        Gdk.MemoryFormat.R8G8B8A8,
        frame.data,
        frame.stride,
    )


def pack_pixels(pixels: np.ndarray) -> bytes:
    return np.ascontiguousarray(pixels, dtype=np.uint8).tobytes()


class Effects:
    def __init__(self) -> None:
        self.history: deque[np.ndarray] = deque(maxlen=HISTORY_FRAMES)
        self.trail: np.ndarray | None = None

    def reset(self) -> None:
        self.history.clear()
        self.trail = None

    def apply(self, name: str, frame: np.ndarray, intensity: float) -> np.ndarray:
        if name == "Original":
            return frame
        if name == "Thermal":
            return self._thermal(frame)
        if name == "Neon edges":
            return self._neon_edges(frame, intensity)
        if name == "Motion trails":
            return self._motion_trails(frame, intensity)
        if name == "Time ribbons":
            return self._time_ribbons(frame, intensity)
        if name == "Mirror drift":
            return self._mirror_drift(frame, intensity)
        return frame

    def _thermal(self, frame: np.ndarray) -> np.ndarray:
        rgb = frame[..., :3].astype(np.int16)
        luma = (54 * rgb[..., 0] + 183 * rgb[..., 1] + 19 * rgb[..., 2]) >> 8

        out = np.empty_like(frame)
        out[..., 0] = np.clip((luma - 85) * 3, 0, 255)
        out[..., 1] = np.clip(255 - np.abs(luma - 128) * 2, 0, 255)
        out[..., 2] = np.clip(255 - luma * 2, 0, 255)
        out[..., 3] = 255
        return out

    def _neon_edges(self, frame: np.ndarray, intensity: float) -> np.ndarray:
        rgb = frame[..., :3].astype(np.int16)
        luma = (54 * rgb[..., 0] + 183 * rgb[..., 1] + 19 * rgb[..., 2]) >> 8

        edge = np.zeros(luma.shape, dtype=np.int16)
        edge[:, 1:-1] += np.abs(luma[:, 2:] - luma[:, :-2])
        edge[1:-1, :] += np.abs(luma[2:, :] - luma[:-2, :])
        edge = np.clip(edge * (1.0 + intensity * 4.0), 0, 255).astype(np.uint8)

        base = (frame[..., :3] * 0.20).astype(np.uint8)
        out = np.empty_like(frame)
        out[..., 0] = np.maximum(base[..., 0], edge)
        out[..., 1] = np.maximum(
            base[..., 1],
            np.clip(edge * 2, 0, 255).astype(np.uint8),
        )
        out[..., 2] = np.maximum(base[..., 2], 255 - edge // 2)
        out[..., 3] = 255
        return out

    def _motion_trails(self, frame: np.ndarray, intensity: float) -> np.ndarray:
        current = frame.astype(np.float32)
        if self.trail is None or self.trail.shape != current.shape:
            self.trail = current
        decay = 0.72 + intensity * 0.25
        self.trail = np.maximum(current, self.trail * decay)
        out = np.clip(self.trail, 0, 255).astype(np.uint8)
        out[..., 3] = 255
        return out

    def _time_ribbons(self, frame: np.ndarray, intensity: float) -> np.ndarray:
        self.history.append(frame.copy())
        if len(self.history) < 2:
            return frame

        out = frame.copy()
        height = frame.shape[0]
        band_count = 18
        band_height = max(1, height // band_count)
        max_delay = max(1, int((len(self.history) - 1) * intensity))

        for band in range(band_count):
            y0 = band * band_height
            y1 = height if band == band_count - 1 else min(height, y0 + band_height)
            delay = min(max_delay, band * max(1, max_delay // band_count + 1))
            out[y0:y1] = self.history[-1 - delay][y0:y1]
        return out

    def _mirror_drift(self, frame: np.ndarray, intensity: float) -> np.ndarray:
        out = frame.copy()
        height, width = frame.shape[:2]
        half = width // 2
        shift = int((np.sin(time.monotonic() * 2.0) * 0.5 + 0.5) * intensity * half)
        left = np.roll(frame[:, :half], shift, axis=1)
        out[:, :half] = left
        out[:, half:] = left[:, ::-1][:, : width - half]

        y = np.arange(height, dtype=np.float32)[:, None]
        tint = (np.sin(y / 18.0 + time.monotonic() * 5.0) * 24.0 * intensity).astype(
            np.int16
        )
        out[..., 1] = np.clip(out[..., 1].astype(np.int16) + tint, 0, 255)
        out[..., 3] = 255
        return out


class ProcessingWorker:
    def __init__(self, pipeline: "MediaPipeline", presenter) -> None:
        self.pipeline = pipeline
        self.presenter = presenter
        self.effects = Effects()
        self.effect_name = "Original"
        self.intensity = 0.65
        self.paused = False
        self.closed = False
        self.pending = False
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self._run, name="media-effects-worker")
        self.thread.start()

    def close(self) -> None:
        with self.condition:
            self.closed = True
            self.condition.notify()
        self.thread.join()

    def notify_sample(self) -> None:
        with self.condition:
            self.pending = True
            self.condition.notify()

    def set_paused(self, paused: bool) -> None:
        with self.condition:
            self.paused = paused
            self.pending = True
            self.condition.notify()

    def set_effect(self, name: str, intensity: float) -> None:
        with self.condition:
            changed = name != self.effect_name
            self.effect_name = name
            self.intensity = intensity
            if changed:
                self.effects.reset()

    def _run(self) -> None:
        while True:
            with self.condition:
                while not self.pending and not self.closed:
                    self.condition.wait()
                if self.closed:
                    return
                self.pending = False
                paused = self.paused
                effect_name = self.effect_name
                intensity = self.intensity

            if paused:
                continue

            try:
                result = self._process_latest(effect_name, intensity)
            except Exception as exc:
                self.presenter(None, str(exc))
                continue

            if result is not None:
                self.presenter(result, None)

    def _process_latest(
        self,
        effect_name: str,
        intensity: float,
    ) -> ProcessedFrame | None:
        latest = None
        copy_ms = 0.0

        while True:
            t0 = time.perf_counter()
            frame = self.pipeline.pull()
            copy_ms += (time.perf_counter() - t0) * 1000.0
            if frame is None:
                break
            latest = frame

        if latest is None:
            return None

        t0 = time.perf_counter()
        processed = self.effects.apply(effect_name, latest.pixels, intensity)
        effect_ms = (time.perf_counter() - t0) * 1000.0

        t0 = time.perf_counter()
        data = pack_pixels(processed)
        pack_ms = (time.perf_counter() - t0) * 1000.0

        return ProcessedFrame(
            data=data,
            width=latest.width,
            height=latest.height,
            stride=latest.stride,
            copy_ms=copy_ms,
            effect_ms=effect_ms,
            pack_ms=pack_ms,
        )


class MediaPipeline:
    def __init__(
        self,
        use_test_source: bool,
        file_path: str | None,
        uri: str | None,
        width: int | None,
        height: int | None,
    ) -> None:
        Gst.init(None)
        if file_path is not None:
            uri = Path(file_path).expanduser().resolve().as_uri()

        if uri is not None:
            self.description = uri
            self._build_uri_pipeline(uri, width, height)
        else:
            self._build_live_pipeline(use_test_source, width, height)

    def _caps_string(self, width: int | None, height: int | None) -> str:
        caps = "video/x-raw,format=RGBA"
        if width is not None:
            caps += f",width={width}"
        if height is not None:
            caps += f",height={height}"
        return caps

    def _make_element(self, factory: str) -> Gst.Element:
        element = Gst.ElementFactory.make(factory)
        if element is None:
            raise RuntimeError(f"could not create GStreamer element: {factory}")
        return element

    def _build_live_pipeline(
        self,
        use_test_source: bool,
        width: int | None,
        height: int | None,
    ) -> None:
        if use_test_source:
            source = "videotestsrc is-live=true pattern=ball"
        else:
            source = "autovideosrc"

        caps = self._caps_string(width, height)
        self.description = (
            f"{source} ! videoconvert ! videoscale ! "
            f"{caps} ! "
            "queue max-size-buffers=1 leaky=downstream ! "
            "appsink name=sink emit-signals=true sync=false max-buffers=1 drop=true"
        )
        self.pipeline = Gst.parse_launch(self.description)
        self.sink = self.pipeline.get_by_name("sink")
        if self.sink is None:
            raise RuntimeError("appsink was not created")

    def _build_uri_pipeline(
        self,
        uri: str,
        width: int | None,
        height: int | None,
    ) -> None:
        self.pipeline = Gst.Pipeline.new()
        source = self._make_element("uridecodebin")
        convert = self._make_element("videoconvert")
        scale = self._make_element("videoscale")
        capsfilter = self._make_element("capsfilter")
        queue = self._make_element("queue")
        self.sink = self._make_element("appsink")

        source.set_property("uri", uri)
        capsfilter.set_property(
            "caps",
            Gst.Caps.from_string(self._caps_string(width, height)),
        )
        queue.set_property("max-size-buffers", 1)
        queue.set_property("leaky", 2)
        self.sink.set_property("emit-signals", True)
        self.sink.set_property("sync", False)
        self.sink.set_property("max-buffers", 1)
        self.sink.set_property("drop", True)

        for element in [source, convert, scale, capsfilter, queue, self.sink]:
            self.pipeline.add(element)

        convert.link(scale)
        scale.link(capsfilter)
        capsfilter.link(queue)
        queue.link(self.sink)

        def on_pad_added(_source: Gst.Element, pad: Gst.Pad) -> None:
            sink_pad = convert.get_static_pad("sink")
            if sink_pad is None or sink_pad.is_linked():
                return

            caps = pad.get_current_caps()
            if caps is not None and not caps.to_string().startswith("video/"):
                return
            pad.link(sink_pad)

        source.connect("pad-added", on_pad_added)

    def start(self) -> None:
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self) -> None:
        self.pipeline.set_state(Gst.State.NULL)

    def connect_new_sample(self, callback) -> int:
        return self.sink.connect("new-sample", callback)

    def disconnect(self, handler_id: int) -> None:
        self.sink.disconnect(handler_id)

    def pull(self) -> Frame | None:
        sample = self.sink.emit("try-pull-sample", 0)
        if sample is None:
            return None

        caps = sample.get_caps()
        structure = caps.get_structure(0)
        width = structure.get_int("width")[1]
        height = structure.get_int("height")[1]
        buffer = sample.get_buffer()
        if buffer is None:
            return None
        return gst_buffer_to_numpy(buffer, width, height)


class NativePipeline:
    def __init__(
        self,
        use_test_source: bool,
        file_path: str | None,
        uri: str | None,
        width: int | None,
        height: int | None,
    ) -> None:
        Gst.init(None)
        if file_path is not None:
            uri = Path(file_path).expanduser().resolve().as_uri()

        if uri is not None:
            self._build_uri_pipeline(uri, width, height)
        else:
            self._build_live_pipeline(use_test_source, width, height)

    def _caps_string(self, width: int | None, height: int | None) -> str | None:
        fields = []
        if width is not None:
            fields.append(f"width={width}")
        if height is not None:
            fields.append(f"height={height}")
        if not fields:
            return None
        return "video/x-raw," + ",".join(fields)

    def _make_element(self, factory: str) -> Gst.Element:
        element = Gst.ElementFactory.make(factory)
        if element is None:
            raise RuntimeError(f"could not create GStreamer element: {factory}")
        return element

    def _configure_sink(self) -> None:
        self.sink.set_property("sync", False)

    def _build_live_pipeline(
        self,
        use_test_source: bool,
        width: int | None,
        height: int | None,
    ) -> None:
        if use_test_source:
            source = "videotestsrc is-live=true pattern=ball"
        else:
            source = "autovideosrc"

        caps = self._caps_string(width, height)
        caps_part = f" ! videoscale ! {caps}" if caps is not None else ""
        self.description = (
            f"{source} ! videoconvert{caps_part} ! "
            "gtk4paintablesink name=sink sync=false"
        )
        self.pipeline = Gst.parse_launch(self.description)
        self.sink = self.pipeline.get_by_name("sink")
        if self.sink is None:
            raise RuntimeError("gtk4paintablesink was not created")

    def _build_uri_pipeline(
        self,
        uri: str,
        width: int | None,
        height: int | None,
    ) -> None:
        self.pipeline = Gst.Pipeline.new()
        source = self._make_element("uridecodebin")
        convert = self._make_element("videoconvert")
        self.sink = self._make_element("gtk4paintablesink")
        self._configure_sink()

        elements = [source, convert]
        caps = self._caps_string(width, height)
        if caps is not None:
            scale = self._make_element("videoscale")
            capsfilter = self._make_element("capsfilter")
            capsfilter.set_property("caps", Gst.Caps.from_string(caps))
            elements.extend([scale, capsfilter])
        elements.append(self.sink)

        source.set_property("uri", uri)
        for element in elements:
            self.pipeline.add(element)

        if caps is None:
            convert.link(self.sink)
        else:
            convert.link(scale)
            scale.link(capsfilter)
            capsfilter.link(self.sink)

        def on_pad_added(_source: Gst.Element, pad: Gst.Pad) -> None:
            sink_pad = convert.get_static_pad("sink")
            if sink_pad is None or sink_pad.is_linked():
                return

            caps = pad.get_current_caps()
            if caps is not None and not caps.to_string().startswith("video/"):
                return
            pad.link(sink_pad)

        source.connect("pad-added", on_pad_added)

    def start(self) -> None:
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self) -> None:
        self.pipeline.set_state(Gst.State.NULL)

    def get_paintable(self):
        return self.sink.get_property("paintable")


class WebcamEffectsWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        pipeline: MediaPipeline,
        width: int | None,
        height: int | None,
        fullscreen: bool,
    ) -> None:
        super().__init__(
            application=application,
            title="Webcam Effects",
            default_width=1280,
            default_height=840,
        )
        self.pipeline = pipeline
        self.requested_width = width
        self.requested_height = height
        self.fullscreen_on_present = fullscreen
        self.effect_names = [
            "Original",
            "Thermal",
            "Neon edges",
            "Motion trails",
            "Time ribbons",
            "Mirror drift",
        ]
        self.paused = False
        self.frames = 0
        self.last_fps_at = time.monotonic()
        self.last_frame_at = self.last_fps_at
        self.present_source_id = 0
        self.present_lock = threading.Lock()
        self.latest_processed_frame: ProcessedFrame | None = None
        self.latest_error: str | None = None
        self.latest_copy_ms = 0.0
        self.latest_effect_ms = 0.0
        self.latest_pack_ms = 0.0

        self._build_ui()
        self.worker = ProcessingWorker(self.pipeline, self._submit_processed)
        self.sample_handler_id = self.pipeline.connect_new_sample(self._on_new_sample)
        self.pipeline.start()

    def close(self) -> None:
        if self.present_source_id:
            GLib.source_remove(self.present_source_id)
            self.present_source_id = 0
        self.worker.close()
        self.pipeline.disconnect(self.sample_handler_id)
        self.pipeline.stop()

    def _build_ui(self) -> None:
        header = Gtk.HeaderBar()
        self.status_label = Gtk.Label(label="starting media")
        header.set_title_widget(self.status_label)
        self.set_titlebar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(8)
        root.set_margin_bottom(8)
        root.set_margin_start(8)
        root.set_margin_end(8)
        self.set_child(root)

        self.picture = Gtk.Picture(
            content_fit=Gtk.ContentFit.CONTAIN,
            can_shrink=True,
            hexpand=True,
            vexpand=True,
        )
        root.append(self.picture)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(controls)

        open_button = Gtk.Button(label="Open")
        open_button.connect("clicked", self._on_open_clicked)
        controls.append(open_button)
        self.open_button = open_button

        self.effect_combo = Gtk.ComboBoxText()
        for name in self.effect_names:
            self.effect_combo.append_text(name)
        self.effect_combo.set_active(0)
        self.effect_combo.connect("changed", self._on_effect_changed)
        controls.append(self.effect_combo)

        self.intensity = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            0.0,
            1.0,
            0.01,
        )
        self.intensity.set_value(0.65)
        self.intensity.set_hexpand(True)
        self.intensity.connect("value-changed", self._on_intensity_changed)
        controls.append(self.intensity)

        pause = Gtk.Button(label="Pause")
        pause.connect("clicked", self._on_pause_clicked)
        controls.append(pause)
        self.pause_button = pause

    def _on_effect_changed(self, *_args) -> None:
        self._sync_worker_effect()

    def _on_intensity_changed(self, *_args) -> None:
        self._sync_worker_effect()

    def _sync_worker_effect(self) -> None:
        self.worker.set_effect(
            self.effect_names[self.effect_combo.get_active()],
            self.intensity.get_value(),
        )

    def _on_open_clicked(self, *_args) -> None:
        dialog = Gtk.FileDialog()
        dialog.open(self, None, self._on_open_dialog_done)
        self.open_dialog = dialog

    def _on_open_dialog_done(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            file_ = dialog.open_finish(result)
        except Exception:
            self.open_dialog = None
            return

        try:
            uri = file_.get_uri()
            if uri is not None:
                self._open_uri(uri)
        except Exception as exc:
            self.status_label.set_label(f"open failed: {exc}")
        finally:
            self.open_dialog = None

    def _open_uri(self, uri: str) -> None:
        pipeline = MediaPipeline(
            use_test_source=False,
            file_path=None,
            uri=uri,
            width=self.requested_width,
            height=self.requested_height,
        )
        self._replace_pipeline(pipeline)

    def _replace_pipeline(self, pipeline: MediaPipeline) -> None:
        self.worker.close()
        self.pipeline.disconnect(self.sample_handler_id)
        self.pipeline.stop()

        self.pipeline = pipeline
        with self.present_lock:
            self.latest_processed_frame = None
            self.latest_error = None
        self.worker = ProcessingWorker(self.pipeline, self._submit_processed)
        self._sync_worker_effect()
        self.sample_handler_id = self.pipeline.connect_new_sample(self._on_new_sample)
        self.frames = 0
        self.last_fps_at = time.monotonic()
        self.last_frame_at = self.last_fps_at
        self.status_label.set_label("starting media")
        self.pipeline.start()

    def _on_pause_clicked(self, *_args) -> None:
        self.paused = not self.paused
        self.worker.set_paused(self.paused)
        self.pause_button.set_label("Resume" if self.paused else "Pause")

    def _on_new_sample(self, *_args) -> Gst.FlowReturn:
        self.worker.notify_sample()
        return Gst.FlowReturn.OK

    def _submit_processed(
        self,
        frame: ProcessedFrame | None,
        error: str | None,
    ) -> None:
        with self.present_lock:
            self.latest_processed_frame = frame
            self.latest_error = error
            if self.present_source_id:
                return
            self.present_source_id = GLib.idle_add(
                self._present_processed,
                priority=GLIB_PRIORITY_DEFAULT_IDLE,
            )

    def _present_processed(self) -> bool:
        with self.present_lock:
            frame = self.latest_processed_frame
            error = self.latest_error
            self.latest_processed_frame = None
            self.latest_error = None
            self.present_source_id = 0

        if error is not None:
            self.status_label.set_label(f"media error: {error}")
            return False

        if frame is None:
            return False

        texture = processed_frame_to_texture(frame)
        self.picture.set_paintable(texture)

        self.frames += 1
        self.latest_copy_ms = frame.copy_ms
        self.latest_effect_ms = frame.effect_ms
        self.latest_pack_ms = frame.pack_ms
        now = time.monotonic()
        if now - self.last_fps_at >= 0.5:
            fps = self.frames / (now - self.last_fps_at)
            self.frames = 0
            self.last_fps_at = now
            name = self.effect_names[self.effect_combo.get_active()]
            self.status_label.set_label(
                f"{name}  {fps:4.1f} fps  {frame.width}x{frame.height}  "
                f"copy {self.latest_copy_ms:4.1f} ms  "
                f"effect {self.latest_effect_ms:4.1f} ms  "
                f"pack {self.latest_pack_ms:4.1f} ms"
            )
        self.last_frame_at = now
        return False


class NativeWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        application: Gtk.Application,
        pipeline: NativePipeline,
        width: int | None,
        height: int | None,
    ) -> None:
        super().__init__(
            application=application,
            title="Native Media Baseline",
            default_width=1280,
            default_height=840,
        )
        self.pipeline = pipeline
        self.requested_width = width
        self.requested_height = height
        self._build_ui()
        self._start_pipeline()

    def close(self) -> None:
        self.pipeline.stop()

    def _build_ui(self) -> None:
        header = Gtk.HeaderBar()
        self.status_label = Gtk.Label(label="native GStreamer display")
        header.set_title_widget(self.status_label)
        self.set_titlebar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root.set_margin_top(8)
        root.set_margin_bottom(8)
        root.set_margin_start(8)
        root.set_margin_end(8)
        self.set_child(root)

        self.picture = Gtk.Picture(
            content_fit=Gtk.ContentFit.CONTAIN,
            can_shrink=True,
            hexpand=True,
            vexpand=True,
        )
        root.append(self.picture)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(controls)

        open_button = Gtk.Button(label="Open")
        open_button.connect("clicked", self._on_open_clicked)
        controls.append(open_button)

    def _start_pipeline(self) -> None:
        self.picture.set_paintable(self.pipeline.get_paintable())
        self.pipeline.start()

    def _on_open_clicked(self, *_args) -> None:
        dialog = Gtk.FileDialog()
        dialog.open(self, None, self._on_open_dialog_done)
        self.open_dialog = dialog

    def _on_open_dialog_done(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            file_ = dialog.open_finish(result)
        except Exception:
            self.open_dialog = None
            return

        try:
            uri = file_.get_uri()
            if uri is not None:
                self._open_uri(uri)
        except Exception as exc:
            self.status_label.set_label(f"open failed: {exc}")
        finally:
            self.open_dialog = None

    def _open_uri(self, uri: str) -> None:
        pipeline = NativePipeline(
            use_test_source=False,
            file_path=None,
            uri=uri,
            width=self.requested_width,
            height=self.requested_height,
        )
        self.pipeline.stop()
        self.pipeline = pipeline
        self._start_pipeline()


def on_activate(app: Gtk.Application, args: argparse.Namespace) -> None:
    try:
        if args.native:
            pipeline = NativePipeline(
                args.test_source,
                args.file,
                args.uri,
                args.width,
                args.height,
            )
        else:
            pipeline = MediaPipeline(
                args.test_source,
                args.file,
                args.uri,
                args.width,
                args.height,
            )
    except Exception as exc:
        win = Gtk.ApplicationWindow(
            application=app,
            title="Webcam Effects",
            default_width=520,
            default_height=120,
        )
        win.set_child(Gtk.Label(label=f"Could not create media pipeline:\n{exc}"))
        app.window = win
        win.present()
        return

    if args.native:
        win = NativeWindow(
            application=app,
            pipeline=pipeline,
            width=args.width,
            height=args.height,
        )
    else:
        win = WebcamEffectsWindow(
            application=app,
            pipeline=pipeline,
            width=args.width,
            height=args.height,
            fullscreen=args.fullscreen,
        )

    def on_close_request(*_args) -> bool:
        win.close()
        app.quit()
        return False

    win.connect("close-request", on_close_request)
    app.window = win
    win.present()
    if args.fullscreen:
        win.fullscreen()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--test-source",
        action="store_true",
        help="use videotestsrc instead of a webcam",
    )
    source.add_argument("--file", help="play a local video file instead of the webcam")
    source.add_argument("--uri", help="play a media URI instead of the webcam")
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="force a capture width; default is the source's negotiated size",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="force a capture height; default is the source's negotiated size",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="display through gtk4paintablesink instead of the NumPy path",
    )
    parser.add_argument("--fullscreen", action="store_true")
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    app = Gtk.Application(
        application_id="dev.goi.WebcamEffects",
        flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
    )
    app.connect("activate", lambda app: on_activate(app, args))
    app.hold()
    signal.signal(
        signal.SIGINT,
        lambda *_args: GLib.idle_add(app.quit, priority=GLIB_PRIORITY_DEFAULT_IDLE),
    )
    return app.run([argv[0]])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
