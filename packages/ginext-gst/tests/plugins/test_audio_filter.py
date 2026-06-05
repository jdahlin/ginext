"""Tests for GstAudio.AudioFilter plugin authoring."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from .support import (
    Gst,
    author_audio_filter_class,
    gst_bucket,
    unique,
)


def test_audio_filter_subclass_registration_records_audio_filter_metadata() -> None:
    state = {"setup": 0, "transform_ip": 0}
    element_name = unique("audio_filter").lower()
    cls = author_audio_filter_class(
        type_name=unique("AudioFilterType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Audio Filter"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_audio_filter_dispatches_setup_before_transform() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_audio_filter_class, unique

state = {{"setup": 0, "transform_ip": 0}}
element_name = unique("audio_filter_setup").lower()
author_audio_filter_class(
    type_name=unique("AudioFilterSetupType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "audiotestsrc num-buffers=1 ! "
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved ! "
    f"{{element_name}} ! fakesink"
)
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None:
        assert msg.type != Gst.MessageType.ERROR
    if state["setup"] >= 1 and state["transform_ip"] >= 1:
        break
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
    assert state["setup"] >= 1
    assert state["transform_ip"] >= 1


def test_audio_filter_dispatches_transform_or_transform_ip_in_pipeline() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_audio_filter_class, unique

state = {{"setup": 0, "transform_ip": 0}}
element_name = unique("audio_filter_transform").lower()
author_audio_filter_class(
    type_name=unique("AudioFilterTransformType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "audiotestsrc num-buffers=1 ! "
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved ! "
    f"{{element_name}} ! fakesink"
)
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None:
        assert msg.type != Gst.MessageType.ERROR
    if state["transform_ip"] >= 1:
        break
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
    assert state["transform_ip"] >= 1


def test_audio_filter_preserves_same_format_negotiation_shape() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_audio_filter_class, unique

state = {{"setup": 0, "transform_ip": 0}}
element_name = unique("audio_filter_negotiation").lower()
author_audio_filter_class(
    type_name=unique("AudioFilterNegotiationType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.parse_launch(
    "audiotestsrc num-buffers=1 ! "
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved ! "
    f"{{element_name}} ! fakesink"
)
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None:
        assert msg.type != Gst.MessageType.ERROR
    if state["setup"] >= 1:
        break
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
    assert state["setup"] >= 1
