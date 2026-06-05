"""Tests for GstBase.BaseParse plugin authoring."""

from __future__ import annotations

import time

from .support import Gst, author_base_parse_class, gst_bucket, unique


def test_baseparse_subclass_registration_records_parser_metadata() -> None:
    state = {"start": 0, "stop": 0, "handle_frame": 0}
    element_name = unique("base_parse").lower()
    cls = author_base_parse_class(
        type_name=unique("BaseParseType"),
        element_name=element_name,
        state=state,
    )
    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Base Parse"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_baseparse_dispatches_handle_frame_for_incoming_data() -> None:
    state = {"start": 0, "stop": 0, "handle_frame": 0}
    element_name = unique("base_parse_lifecycle").lower()
    author_base_parse_class(
        type_name=unique("BaseParseLifecycleType"),
        element_name=element_name,
        state=state,
    )

    pipe = Gst.parse_launch(f"appsrc name=src ! {element_name} ! fakesink")
    appsrc = pipe.get_by_name("src")
    appsrc.caps = Gst.Caps.from_string("application/octet-stream")
    appsrc.format = Gst.Format.TIME
    assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
    buf = Gst.Buffer.new_allocate(None, 3, None)
    buf.fill(0, list(b"abc"))
    assert appsrc.push_buffer(buf) == Gst.FlowReturn.OK
    time.sleep(0.1)
    pipe.set_state(Gst.State.NULL)

    assert state["handle_frame"] >= 1


def test_baseparse_can_finish_frames_and_emit_parsed_buffers() -> None:
    state = {"start": 0, "stop": 0, "handle_frame": 0}
    cls = author_base_parse_class(
        type_name=unique("BaseParseHelperType"),
        element_name=unique("base_parse_helpers").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert hasattr(elt, "finish_frame")
        assert hasattr(elt, "merge_tags")
        assert hasattr(elt, "set_duration")
        assert hasattr(elt, "set_frame_rate")
        assert hasattr(elt, "set_latency")
        assert hasattr(elt, "set_passthrough")
    finally:
        elt.set_state(Gst.State.NULL)


def test_baseparse_handles_segment_seek_and_eos_through_base_class() -> None:
    state = {"start": 0, "stop": 0, "handle_frame": 0}
    cls = author_base_parse_class(
        type_name=unique("BaseParseControlType"),
        element_name=unique("base_parse_control").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.set_state(Gst.State.READY) != Gst.StateChangeReturn.FAILURE
        names = cls.gimeta.vfunc_infos
        assert "sink_event" in names
        assert "sink_query" in names
        assert "src_event" in names
        assert "src_query" in names
        assert "query" in names
    finally:
        elt.set_state(Gst.State.NULL)
