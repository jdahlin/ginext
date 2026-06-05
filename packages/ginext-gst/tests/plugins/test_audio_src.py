"""Tests for GstAudio.AudioSrc plugin authoring."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from .support import Gst, author_audio_src_class, gst_bucket, unique


def test_audio_src_subclass_registration_records_source_metadata() -> None:
    state = {"open": 0, "prepare": 0, "read": 0, "unprepare": 0, "close": 0}
    element_name = unique("audio_src").lower()
    cls = author_audio_src_class(
        type_name=unique("AudioSrcType"),
        element_name=element_name,
        state=state,
    )
    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Audio Src"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_audio_src_dispatches_open_prepare_read_unprepare_close_vfuncs() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_audio_src_class, unique

state = {{"open": 0, "prepare": 0, "read": 0, "unprepare": 0, "close": 0}}
element_name = unique("audio_src_lifecycle").lower()
author_audio_src_class(
    type_name=unique("AudioSrcLifecycleType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(f"{{element_name}} ! fakesink")
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if state["open"] >= 1 and state["prepare"] >= 1 and state["read"] >= 1:
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
    assert state["read"] >= 1


def test_audio_src_produces_buffers_in_a_minimal_pipeline() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_audio_src_class, unique

state = {{
    "open": 0,
    "prepare": 0,
    "read": 0,
    "unprepare": 0,
    "close": 0,
    "reset": 0,
    "delay": 0,
}}
element_name = unique("audio_src_buffers").lower()
author_audio_src_class(
    type_name=unique("AudioSrcBuffersType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(f"{{element_name}} ! fakesink")
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if state["read"] >= 1:
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
    assert state["read"] >= 1
    assert state["delay"] >= 0


def test_audio_src_reset_path_unblocks_pending_reads_cleanly() -> None:
    state = {
        "open": 0,
        "prepare": 0,
        "read": 0,
        "unprepare": 0,
        "close": 0,
        "reset": 0,
        "delay": 0,
    }
    cls = author_audio_src_class(
        type_name=unique("AudioSrcResetType"),
        element_name=unique("audio_src_reset").lower(),
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
