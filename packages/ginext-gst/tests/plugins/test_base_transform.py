# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for GstBase.BaseTransform plugin authoring."""

from __future__ import annotations

import json
import pathlib
import pytest
import subprocess
import sys

import ginext

from ginext import Gst

from .support import (
    author_element_class,
    author_transform_chainup_send_event_class,
    author_transform_class,
    gst_bucket,
    make_src_sink_templates,
    raw_audio_caps,
    unique,
)


def test_basetransform_subclass_runs_in_pipeline_and_dispatches_vfuncs() -> None:
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_transform_class, unique

state = {{
    "transform_ip": 0,
    "change_state": 0,
    "send_event": 0,
    "query": 0,
}}
element_name = unique("pipeline_transform").lower()
author_transform_class(
    type_name=unique("PipelineTransformType"),
    element_name=element_name,
    state=state,
)
pipe = Gst.parse_launch(
    "audiotestsrc num-buffers=3 ! "
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
    if msg is not None and msg.type == Gst.MessageType.ERROR:
        raise AssertionError(msg.parse_error())
    if state["transform_ip"] >= 3 and state["change_state"] > 0:
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
    assert state["transform_ip"] == 3
    assert state["change_state"] > 0


def test_element_send_event_and_query_dispatch_to_python_overrides() -> None:
    state = {
        "transform_ip": 0,
        "change_state": 0,
        "send_event": 0,
        "query": 0,
    }
    element_name = unique("event_query_transform").lower()
    cls = author_transform_class(
        type_name=unique("EventQueryType"),
        element_name=element_name,
        state=state,
    )
    elt = cls()

    assert elt.send_event(Gst.Event.new_eos()) is True
    assert elt.query(Gst.Query.new_duration(Gst.Format.TIME)) is False
    assert state["send_event"] == 1
    assert state["query"] == 1


def test_element_query_chainup_accepts_direction_and_boxed_query_arguments() -> None:
    state = {
        "transform_ip": 0,
        "change_state": 0,
        "send_event": 0,
        "query": 0,
    }
    cls = author_transform_class(
        type_name=unique("QueryChainupType"),
        element_name=unique("query_chainup_transform").lower(),
        state=state,
    )
    elt = cls()

    assert elt.query(Gst.Query.new_duration(Gst.Format.TIME)) is False
    assert state["query"] == 1


def test_ambiguous_do_query_on_basetransform_requires_explicit_base_name() -> None:
    with pytest.raises(TypeError, match="do_query"):
        author_element_class(
            base_cls=ginext.GstBase.BaseTransform,
            type_name=unique("AmbiguousQueryType"),
            element_name=unique("ambiguous_query_transform").lower(),
            methods={
                "do_query": lambda self, direction, query: False,
                "do_transform_ip": lambda self, buf: Gst.FlowReturn.OK,
            },
            metadata={
                "longname": "Python Ambiguous Query Transform",
                "classification": "Filter/Effect",
                "description": "probe",
                "author": "ginext",
            },
            pad_templates=make_src_sink_templates(raw_audio_caps(), raw_audio_caps()),
        )


def test_explicit_do_base_transform_query_binds_the_basetransform_vfunc() -> None:
    state = {"query": 0, "transform_ip": 0}
    element_name = unique("explicit_query_transform").lower()

    def do_base_transform_query(
        self: ginext.GstBase.BaseTransform,
        direction: Gst.PadDirection,
        query: Gst.Query,
    ) -> bool:
        state["query"] += 1
        return False

    def do_transform_ip(
        self: ginext.GstBase.BaseTransform, buf: Gst.Buffer
    ) -> Gst.FlowReturn:
        state["transform_ip"] += 1
        return Gst.FlowReturn.OK

    cls = author_element_class(
        base_cls=ginext.GstBase.BaseTransform,
        type_name=unique("ExplicitQueryType"),
        element_name=element_name,
        methods={
            "do_base_transform_query": do_base_transform_query,
            "do_transform_ip": do_transform_ip,
        },
        metadata={
            "longname": "Python Explicit Query Transform",
            "classification": "Filter/Effect",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_src_sink_templates(raw_audio_caps(), raw_audio_caps()),
    )
    elt = cls()

    assert elt.query(Gst.Query.new_duration(Gst.Format.TIME)) is False
    assert state["query"] == 1


def test_element_send_event_chainup_marshals_boxed_event_arguments() -> None:
    state = {
        "send_event": 0,
    }
    cls = author_transform_chainup_send_event_class(
        type_name=unique("EventChainupType"),
        element_name=unique("event_chainup_transform").lower(),
        state=state,
    )
    elt = cls()

    assert elt.send_event(Gst.Event.new_eos()) is False
    assert state["send_event"] == 1


def test_basetransform_subclass_registration_records_metadata_and_pad_templates() -> (
    None
):
    state = {
        "transform_ip": 0,
        "change_state": 0,
        "send_event": 0,
        "query": 0,
    }
    element_name = unique("meta_transform").lower()
    cls = author_transform_class(
        type_name=unique("MetaTransformType"),
        element_name=element_name,
        state=state,
    )
    bucket = gst_bucket(cls)

    assert bucket["element_metadata"]["longname"] == "Python Transform"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]


def test_basetransform_factory_registration_exposes_elementfactory_metadata() -> None:
    state = {
        "transform_ip": 0,
        "change_state": 0,
        "send_event": 0,
        "query": 0,
    }
    element_name = unique("factory_transform").lower()
    author_transform_class(
        type_name=unique("FactoryTransformType"),
        element_name=element_name,
        state=state,
    )
    factory = Gst.ElementFactory.find(element_name)

    assert factory is not None
    assert factory.get_longname() == "Python Transform"


def test_basetransform_passthrough_or_negotiation_behavior_is_documented_by_a_smoke_case() -> (
    None
):
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import Gst, author_transform_class, unique

state = {{
    "transform_ip": 0,
    "change_state": 0,
    "send_event": 0,
    "query": 0,
}}
element_name = unique("negotiation_transform").lower()
author_transform_class(
    type_name=unique("NegotiationTransformType"),
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
msg_type = None
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None:
        msg_type = int(msg.type)
        if msg.type == Gst.MessageType.ERROR:
            raise AssertionError(msg.parse_error())
    if state["change_state"] > 0 and state["transform_ip"] >= 1:
        break
    time.sleep(0.01)
else:
    raise AssertionError(state)

print(json.dumps({{"state": state, "msg_type": msg_type}}))
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
    payload = json.loads(proc.stdout.strip())
    state = payload["state"]
    assert state["change_state"] > 0
    assert state["transform_ip"] >= 1
