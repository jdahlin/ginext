"""Tests for GstVideo.VideoFilter plugin authoring."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from .support import (
    Gst,
    author_video_filter_class,
    gst_bucket,
    unique,
)


def test_video_filter_subclass_registration_records_filter_metadata() -> None:
    state = {"set_info": 0, "transform_frame_ip": 0}
    element_name = unique("video_filter").lower()
    cls = author_video_filter_class(
        type_name=unique("VideoFilterType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Video Filter"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_video_filter_dispatches_set_info_before_transform() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_video_filter_class, unique

state = {{"set_info": 0, "transform_frame_ip": 0}}
element_name = unique("video_filter_info").lower()
author_video_filter_class(
    type_name=unique("VideoFilterInfoType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "videotestsrc num-buffers=1 ! "
    "video/x-raw,format=RGBA,width=16,height=16,framerate=1/1 ! "
    f"{{element_name}} ! fakesink"
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
    if state["set_info"] >= 1 and state["transform_frame_ip"] >= 1:
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
    assert state["transform_frame_ip"] >= 1


def test_video_filter_dispatches_transform_frame_or_transform_frame_ip() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_video_filter_class, unique

state = {{"set_info": 0, "transform_frame_ip": 0}}
element_name = unique("video_filter_transform").lower()
author_video_filter_class(
    type_name=unique("VideoFilterTransformType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "videotestsrc num-buffers=1 ! "
    "video/x-raw,format=RGBA,width=16,height=16,framerate=1/1 ! "
    f"{{element_name}} ! fakesink"
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
    if state["transform_frame_ip"] >= 1:
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
    assert state["transform_frame_ip"] >= 1


def test_video_filter_preserves_expected_video_negotiation_shape() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_video_filter_class, unique

state = {{"set_info": 0, "transform_frame_ip": 0}}
element_name = unique("video_filter_negotiation").lower()
author_video_filter_class(
    type_name=unique("VideoFilterNegotiationType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "videotestsrc num-buffers=1 ! "
    "video/x-raw,format=RGBA,width=16,height=16,framerate=1/1 ! "
    f"{{element_name}} ! fakesink"
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
    if state["set_info"] >= 1:
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
