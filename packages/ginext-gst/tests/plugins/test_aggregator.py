# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for GstBase.Aggregator plugin authoring."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from .support import (
    Gst,
    GstBase,
    any_caps,
    author_element_class,
    author_aggregator_class,
    gst_bucket,
    make_request_sink_templates,
    unique,
)


def test_aggregator_subclass_registration_records_metadata_and_pad_templates() -> None:
    """Registers an Aggregator subclass with request sink pads and source output."""
    state = {"aggregate": 0}
    element_name = unique("aggregator").lower()
    cls = author_aggregator_class(
        type_name=unique("AggregatorType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Aggregator"
    assert [templ.name_template for templ in bucket["pad_templates"]] == [
        "sink_%u",
        "src",
    ]
    assert Gst.ElementFactory.find(element_name) is not None


def test_aggregator_exposes_request_sink_templates_for_future_mixing_tests() -> None:
    """Verifies the authored request sink template shape expected by aggregator tests."""
    state = {"aggregate": 0}
    cls = author_aggregator_class(
        type_name=unique("AggregatorTemplateType"),
        element_name=unique("aggregator_template").lower(),
        state=state,
    )
    bucket = gst_bucket(cls)

    assert bucket["pad_templates"][0].presence == Gst.PadPresence.REQUEST
    assert bucket["pad_templates"][0].direction == Gst.PadDirection.SINK
    assert bucket["pad_templates"][1].direction == Gst.PadDirection.SRC


def test_aggregator_exposes_expected_authoring_vfunc_surface() -> None:
    """Checks the core authoring vfuncs described by the Aggregator API."""
    names = GstBase.Aggregator.gimeta.vfunc_infos
    assert "aggregate" in names
    assert "clip" in names
    assert "get_next_time" in names
    assert "negotiate" in names
    assert "sink_event" in names
    assert "sink_query" in names

    pad_names = GstBase.AggregatorPad.gimeta.vfunc_infos
    assert "flush" in pad_names
    assert "skip_buffer" in pad_names


def test_aggregator_pad_exposes_buffer_event_and_query_helpers() -> None:
    """Checks the helper methods documented for authored AggregatorPad handling."""
    names = dir(GstBase.AggregatorPad)
    assert "has_buffer" in names
    assert "peek_buffer" in names
    assert "pop_buffer" in names
    assert "drop_buffer" in names
    assert "send_event" in names
    assert "push_event" in names
    assert "query" in names
    assert "query_caps" in names
    assert "query_convert" in names
    assert "query_duration" in names
    assert "query_position" in names


def test_aggregator_request_pads_are_concrete_aggregator_pads() -> None:
    """Verifies the generic Aggregator request-pad surface matches the muxer-style API."""
    state = {"aggregate": 0}
    element_name = unique("aggregator_pads").lower()
    author_aggregator_class(
        type_name=unique("AggregatorPadsType"),
        element_name=element_name,
        state=state,
    )

    agg = Gst.ElementFactory.make(element_name)
    pad1 = agg.request_pad("sink_%u", "sink_7")
    pad2 = agg.request_pad("sink_%u")
    try:
        assert type(pad1).__name__ == "AggregatorPad"
        assert type(pad2).__name__ == "AggregatorPad"
        assert pad1.get_name() == "sink_7"
        assert pad2.get_name().startswith("sink_")
        assert pad1.get_name() != pad2.get_name()
        assert pad1.get_parent() is agg
        assert pad1.get_pad_template_caps().to_string() == "application/octet-stream"
    finally:
        agg.release_request_pad(pad1)
        agg.release_request_pad(pad2)


def test_aggregator_element_send_event_dispatches_to_python_override() -> None:
    """Verifies Aggregator element events dispatch through the Python vfunc override."""
    state = {"aggregate": 0, "send_event": 0}

    def do_aggregate(self: GstBase.Aggregator, timeout: bool) -> Gst.FlowReturn:
        return Gst.FlowReturn.OK

    def do_send_event(self: GstBase.Aggregator, event: Gst.Event) -> bool:
        state["send_event"] += 1
        return True

    cls = author_element_class(
        base_cls=GstBase.Aggregator,
        type_name=unique("AggregatorSendEventType"),
        element_name=unique("aggregator_send_event").lower(),
        methods={
            "do_aggregate": do_aggregate,
            "do_send_event": do_send_event,
        },
        metadata={
            "longname": "Python Aggregator Send Event",
            "classification": "Generic",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_request_sink_templates(any_caps(), any_caps(), "sink_%u"),
    )
    elt = cls()

    assert (
        elt.send_event(
            Gst.Event.new_seek(
                1.0,
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH,
                Gst.SeekType.SET,
                0,
                Gst.SeekType.NONE,
                -1,
            )
        )
        is True
    )
    assert state["send_event"] == 1


def test_aggregator_sink_and_src_queries_dispatch_to_python_overrides() -> None:
    """Verifies Aggregator sink-pad and src-pad queries dispatch to the Python vfuncs."""
    state = {"aggregate": 0, "sink_query": 0, "src_query": 0}
    element_name = unique("aggregator_query").lower()
    caps = Gst.Caps.new_empty()

    def do_aggregate(self: GstBase.Aggregator, timeout: bool) -> Gst.FlowReturn:
        return Gst.FlowReturn.OK

    def do_sink_query(
        self: GstBase.Aggregator,
        aggregator_pad: GstBase.AggregatorPad,
        query: Gst.Query,
    ) -> bool:
        state["sink_query"] += 1
        return False

    def do_src_query(self: GstBase.Aggregator, query: Gst.Query) -> bool:
        state["src_query"] += 1
        return False

    author_element_class(
        base_cls=GstBase.Aggregator,
        type_name=unique("AggregatorQueryType"),
        element_name=element_name,
        methods={
            "do_aggregate": do_aggregate,
            "do_sink_query": do_sink_query,
            "do_src_query": do_src_query,
        },
        metadata={
            "longname": "Python Aggregator Query",
            "classification": "Generic",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_request_sink_templates(any_caps(), any_caps(), "sink_%u"),
    )

    elt = Gst.ElementFactory.make(element_name)
    sinkpad = elt.request_pad("sink_%u")
    srcpad = elt.get_static_pad("src")
    try:
        assert srcpad is not None
        assert sinkpad.query(Gst.Query.new_caps(caps)) is False
        assert srcpad.query(Gst.Query.new_caps(caps)) is False
    finally:
        elt.release_request_pad(sinkpad)

    assert state["sink_query"] == 1
    assert state["src_query"] == 1


def test_aggregator_pipeline_dispatches_sink_event_and_sink_query() -> None:
    """Verifies live upstream traffic reaches the Aggregator sink event/query hooks."""
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import (
    Gst,
    GstBase,
    any_caps,
    author_element_class,
    make_appsrc,
    make_request_sink_templates,
    push_buffers_and_eos,
    unique,
)

state = {{"aggregate": 0, "sink_event": 0, "sink_query": 0}}
element_name = unique("aggregator_pipeline_hooks").lower()
author_element_class(
    base_cls=GstBase.Aggregator,
    type_name=unique("AggregatorPipelineHooksType"),
    element_name=element_name,
    methods={{
        "do_aggregate": lambda self, timeout: (
            state.__setitem__("aggregate", state["aggregate"] + 1)
            or Gst.FlowReturn.OK
        ),
        "do_sink_event": lambda self, pad, event: (
            state.__setitem__("sink_event", state["sink_event"] + 1) or True
        ),
        "do_sink_query": lambda self, pad, query: (
            state.__setitem__("sink_query", state["sink_query"] + 1) or False
        ),
    }},
    metadata={{
        "longname": "Python Aggregator Pipeline Hooks",
        "classification": "Generic",
        "description": "probe",
        "author": "ginext",
    }},
    pad_templates=make_request_sink_templates(any_caps(), any_caps(), "sink_%u"),
)

pipe = Gst.Pipeline()
src = make_appsrc(caps=any_caps(), name="src")
agg = Gst.ElementFactory.make(element_name, "agg")
sink = Gst.ElementFactory.make("fakesink", "sink")
pipe.add(src, agg, sink)

pad = agg.request_pad("sink_%u")
assert src.get_static_pad("src").link(pad) == Gst.PadLinkReturn.OK
assert agg.link(sink) is True

assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
push_buffers_and_eos(src, [b"a"])
bus = pipe.get_bus()
deadline = time.monotonic() + 1.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None:
        assert msg.type != Gst.MessageType.ERROR
    if (
        state["aggregate"] >= 1
        and state["sink_event"] >= 1
        and state["sink_query"] >= 1
    ):
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
    assert state["aggregate"] >= 1
    assert state["sink_event"] >= 1
    assert state["sink_query"] >= 1


def test_aggregator_dispatches_aggregate_when_driven_by_multiple_sink_pads() -> None:
    """Verifies a two-input pipeline drives the Python aggregate vfunc."""
    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import (
    Gst,
    any_caps,
    author_aggregator_class,
    make_appsrc,
    push_buffers_and_eos,
    unique,
)

state = {{"aggregate": 0}}
element_name = unique("aggregator_runtime").lower()
author_aggregator_class(
    type_name=unique("AggregatorRuntimeType"),
    element_name=element_name,
    state=state,
)

pipe = Gst.Pipeline()
src1 = make_appsrc(caps=any_caps(), name="src1")
src2 = make_appsrc(caps=any_caps(), name="src2")
agg = Gst.ElementFactory.make(element_name, "agg")
sink = Gst.ElementFactory.make("fakesink", "sink")
pipe.add(src1, src2, agg, sink)

pad1 = agg.request_pad("sink_%u")
pad2 = agg.request_pad("sink_%u")
assert src1.get_static_pad("src").link(pad1) == Gst.PadLinkReturn.OK
assert src2.get_static_pad("src").link(pad2) == Gst.PadLinkReturn.OK
assert agg.link(sink) is True

assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
push_buffers_and_eos(src1, [b"a"])
push_buffers_and_eos(src2, [b"b"])
bus = pipe.get_bus()
deadline = time.monotonic() + 1.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None:
        assert msg.type != Gst.MessageType.ERROR
    if state["aggregate"] >= 1:
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
    assert state["aggregate"] >= 1


def test_aggregator_finish_buffer_accepts_output_buffer() -> None:
    """Verifies an Aggregator subclass can hand a buffer to finish_buffer()."""
    state = {"aggregate": 0, "pushed": 0}
    element_name = unique("aggregator_output").lower()

    def do_aggregate(self: GstBase.Aggregator, timeout: bool) -> Gst.FlowReturn:
        state["aggregate"] += 1
        if state["pushed"] == 0:
            buf = Gst.Buffer.new_allocate(None, 1, None)
            buf.fill(0, list(b"x"))
            state["pushed"] += 1
            assert self.finish_buffer(buf) == Gst.FlowReturn.OK
            return Gst.FlowReturn.OK
        return Gst.FlowReturn.EOS

    cls = author_element_class(
        base_cls=GstBase.Aggregator,
        type_name=unique("AggregatorOutputType"),
        element_name=element_name,
        methods={"do_aggregate": do_aggregate},
        metadata={
            "longname": "Python Aggregator Output",
            "classification": "Generic",
            "description": "probe",
            "author": "ginext",
        },
        pad_templates=make_request_sink_templates(any_caps(), any_caps(), "sink_%u"),
    )
    elt = cls()
    try:
        assert hasattr(elt, "finish_buffer")
        assert hasattr(elt, "finish_buffer_list")
        assert hasattr(elt, "selected_samples")
        assert hasattr(elt, "peek_next_sample")
        assert hasattr(elt, "get_force_live")
        assert hasattr(elt, "set_force_live")
        assert hasattr(elt, "get_ignore_inactive_pads")
        assert hasattr(elt, "set_ignore_inactive_pads")
        assert hasattr(elt, "get_latency")
        assert hasattr(elt, "set_latency")
        assert hasattr(elt, "set_src_caps")
        assert hasattr(elt, "push_src_event")
        assert elt.get_force_live() is False
        assert elt.set_force_live(True) is None
        assert elt.get_ignore_inactive_pads() is False
        assert elt.set_ignore_inactive_pads(True) is None
        assert elt.get_latency() == 0
        assert elt.set_latency(1, 2) is None
        assert elt.negotiate() is True
    finally:
        elt.set_state(Gst.State.NULL)

    support_dir = pathlib.Path(__file__).resolve().parent
    code = f"""
import json
import os
import sys
import time

sys.path.insert(0, {str(support_dir)!r})
from support import (
    Gst,
    GstBase,
    any_caps,
    author_element_class,
    make_appsrc,
    make_request_sink_templates,
    unique,
)

state = {{"aggregate": 0, "pushed": 0}}
element_name = {element_name!r}

def do_aggregate(self, timeout):
    state["aggregate"] += 1
    if state["pushed"] == 0:
        buf = Gst.Buffer.new_allocate(None, 1, None)
        buf.fill(0, b"x")
        state["pushed"] += 1
        assert self.finish_buffer(buf) == Gst.FlowReturn.OK
        return Gst.FlowReturn.OK
    return Gst.FlowReturn.EOS

author_element_class(
    base_cls=GstBase.Aggregator,
    type_name=unique("AggregatorOutputRuntimeType"),
    element_name=element_name,
    methods={{"do_aggregate": do_aggregate}},
    metadata={{
        "longname": "Python Aggregator Output",
        "classification": "Generic",
        "description": "probe",
        "author": "ginext",
    }},
    pad_templates=make_request_sink_templates(any_caps(), any_caps(), "sink_%u"),
)

pipe = Gst.Pipeline()
src1 = make_appsrc(caps=any_caps(), name="src1")
src2 = make_appsrc(caps=any_caps(), name="src2")
agg = Gst.ElementFactory.make(element_name, "agg")
sink = Gst.ElementFactory.make("fakesink", "sink")
pipe.add(src1, src2, agg, sink)

pad1 = agg.request_pad("sink_%u")
pad2 = agg.request_pad("sink_%u")
assert src1.get_static_pad("src").link(pad1) == Gst.PadLinkReturn.OK
assert src2.get_static_pad("src").link(pad2) == Gst.PadLinkReturn.OK
assert agg.link(sink) is True

assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
for src, payload in ((src1, b"a"), (src2, b"b")):
    buf = Gst.Buffer.new_allocate(None, len(payload), None)
    buf.fill(0, payload)
    assert src.push_buffer(buf) == Gst.FlowReturn.OK
    src.end_of_stream()

bus = pipe.get_bus()
deadline = time.monotonic() + 2.0
while time.monotonic() < deadline:
    msg = bus.timed_pop_filtered(
        50 * Gst.MSECOND, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg is not None:
        assert msg.type != Gst.MessageType.ERROR
    if state["aggregate"] >= 2 and state["pushed"] == 1:
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
    assert state["aggregate"] >= 2
    assert state["pushed"] == 1
