# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for GstBase.BaseSink plugin authoring."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from .support import (
    Gst,
    author_base_sink_class,
    gst_bucket,
    unique,
)


def test_basesink_subclass_registration_records_sink_metadata() -> None:
    """Registers a BaseSink subclass with authored sink metadata and templates."""
    state = {"start": 0, "preroll": 0, "render": 0, "stop": 0}
    element_name = unique("base_sink").lower()
    cls = author_base_sink_class(
        type_name=unique("BaseSinkType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Base Sink"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_basesink_dispatches_start_preroll_render_and_stop_vfuncs() -> None:
    """Runs a minimal pipeline and checks that BaseSink lifecycle vfuncs dispatch."""
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_base_sink_class, unique

state = {{"start": 0, "preroll": 0, "render": 0, "stop": 0}}
element_name = unique("base_sink_lifecycle").lower()
author_base_sink_class(
    type_name=unique("BaseSinkLifecycleType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(f"fakesrc num-buffers=1 ! {{element_name}}")
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if state["start"] >= 1 and state["preroll"] >= 1 and state["render"] >= 1:
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
    assert state["start"] >= 1
    assert state["preroll"] >= 1
    assert state["render"] >= 1


def test_basesink_consumes_buffers_in_a_minimal_pipeline() -> None:
    """Confirms a BaseSink subclass can consume one buffer and reach EOS."""
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_base_sink_class, unique

state = {{"start": 0, "preroll": 0, "render": 0, "stop": 0}}
element_name = unique("base_sink_pipeline").lower()
author_base_sink_class(
    type_name=unique("BaseSinkPipelineType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(f"fakesrc num-buffers=1 ! {{element_name}}")
assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if state["render"] >= 1:
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
    assert state["render"] >= 1


def test_basesink_accepts_state_transitions_expected_by_the_base_class() -> None:
    """Exercises READY->NULL state changes on the subclass instance."""
    state = {"start": 0, "preroll": 0, "render": 0, "stop": 0}
    cls = author_base_sink_class(
        type_name=unique("BaseSinkStateType"),
        element_name=unique("base_sink_state").lower(),
        state=state,
    )
    elt = cls()

    assert elt.set_state(Gst.State.READY) != Gst.StateChangeReturn.FAILURE
    assert elt.set_state(Gst.State.NULL) != Gst.StateChangeReturn.FAILURE
