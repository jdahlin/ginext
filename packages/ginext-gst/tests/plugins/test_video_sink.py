"""Tests for GstVideo.VideoSink plugin authoring."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from .support import (
    Gst,
    author_video_sink_class,
    gst_bucket,
    unique,
)


def test_video_sink_subclass_registration_records_sink_metadata() -> None:
    state = {"set_info": 0, "show_frame": 0}
    element_name = unique("video_sink").lower()
    cls = author_video_sink_class(
        type_name=unique("VideoSinkType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Video Sink"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_video_sink_dispatches_set_info_and_show_frame_vfuncs() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_video_sink_class, unique

state = {{"set_info": 0, "show_frame": 0}}
element_name = unique("video_sink_info").lower()
author_video_sink_class(
    type_name=unique("VideoSinkInfoType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "videotestsrc num-buffers=1 ! "
    "video/x-raw,format=RGBA,width=16,height=16,framerate=1/1 ! "
    f"{{element_name}}"
)
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if state["set_info"] >= 1 and state["show_frame"] >= 1:
        break
    time.sleep(0.01)
else:
    raise AssertionError(state)

print(json.dumps(state))
sys.stdout.flush()
os._exit(0)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    state = json.loads(proc.stdout.strip())
    assert state["set_info"] >= 1
    assert state["show_frame"] >= 1


def test_video_sink_consumes_frames_in_a_minimal_video_pipeline() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_video_sink_class, unique

state = {{"set_info": 0, "show_frame": 0}}
element_name = unique("video_sink_pipeline").lower()
author_video_sink_class(
    type_name=unique("VideoSinkPipelineType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "videotestsrc num-buffers=1 ! "
    "video/x-raw,format=RGBA,width=16,height=16,framerate=1/1 ! "
    f"{{element_name}}"
)
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if state["show_frame"] >= 1:
        break
    time.sleep(0.01)
else:
    raise AssertionError(state)

print(json.dumps(state))
sys.stdout.flush()
os._exit(0)
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    state = json.loads(proc.stdout.strip())
    assert state["show_frame"] >= 1


def test_video_sink_integrates_with_preroll_and_render_control_flow() -> None:
    state = {"set_info": 0, "show_frame": 0}
    cls = author_video_sink_class(
        type_name=unique("VideoSinkStateType"),
        element_name=unique("video_sink_state").lower(),
        state=state,
    )
    elt = cls()

    assert elt.set_state(Gst.State.READY) != Gst.StateChangeReturn.FAILURE
    assert elt.set_state(Gst.State.NULL) != Gst.StateChangeReturn.FAILURE
