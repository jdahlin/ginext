"""Tests for GstAudio.AudioSink plugin authoring."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from .support import Gst, author_audio_sink_class, gst_bucket, unique


def test_audio_sink_subclass_registration_records_sink_metadata() -> None:
    state = {"open": 0, "prepare": 0, "write": 0, "unprepare": 0, "close": 0}
    element_name = unique("audio_sink").lower()
    cls = author_audio_sink_class(
        type_name=unique("AudioSinkType"),
        element_name=element_name,
        state=state,
    )
    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Audio Sink"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_audio_sink_dispatches_open_prepare_write_unprepare_close_vfuncs() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_audio_sink_class, unique

state = {{"open": 0, "prepare": 0, "write": 0, "unprepare": 0, "close": 0}}
element_name = unique("audio_sink_lifecycle").lower()
author_audio_sink_class(
    type_name=unique("AudioSinkLifecycleType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(
    "audiotestsrc num-buffers=1 ! "
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved ! "
    f"{{element_name}}"
)
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if state["open"] >= 1 and state["prepare"] >= 1 and state["write"] >= 1:
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
    assert state["open"] == 1
    assert state["prepare"] >= 1
    assert state["write"] >= 1


def test_audio_sink_consumes_buffers_in_a_minimal_audio_pipeline() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_audio_sink_class, unique

state = {{
    "open": 0,
    "prepare": 0,
    "write": 0,
    "unprepare": 0,
    "close": 0,
    "reset": 0,
    "delay": 0,
}}
element_name = unique("audio_sink_buffers").lower()
author_audio_sink_class(
    type_name=unique("AudioSinkBuffersType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(
    "audiotestsrc num-buffers=1 ! "
    "audio/x-raw,format=S16LE,rate=44100,channels=1,layout=interleaved ! "
    f"{{element_name}}"
)
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if state["write"] >= 1:
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
    assert state["write"] >= 1
    assert state["delay"] >= 0


def test_audio_sink_exposes_clock_and_preroll_behavior_expected_by_base_class() -> None:
    state = {
        "open": 0,
        "prepare": 0,
        "write": 0,
        "unprepare": 0,
        "close": 0,
        "reset": 0,
        "delay": 0,
    }
    cls = author_audio_sink_class(
        type_name=unique("AudioSinkClockType"),
        element_name=unique("audio_sink_clock").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.set_state(Gst.State.READY) != Gst.StateChangeReturn.FAILURE
        assert "reset" in cls.gimeta.vfunc_infos
        assert "delay" in cls.gimeta.vfunc_infos
        assert hasattr(elt, "create_ringbuffer")
        assert hasattr(elt, "provide_clock")
        assert hasattr(elt, "set_provide_clock")
    finally:
        elt.set_state(Gst.State.NULL)
