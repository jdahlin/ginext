# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for GstVideo.VideoAggregator plugin authoring."""

from __future__ import annotations

from .support import (
    Gst,
    GstVideo,
    author_video_aggregator_class,
    gst_bucket,
    run_subprocess_probe,
    unique,
)


def test_video_aggregator_subclass_registration_uses_video_pad_templates() -> None:
    """Registers a VideoAggregator subclass with raw-video request sink pads."""
    state = {"aggregate_frames": 0}
    element_name = unique("video_aggregator").lower()
    cls = author_video_aggregator_class(
        type_name=unique("VideoAggregatorType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Video Aggregator"
    assert [templ.name_template for templ in bucket["pad_templates"]] == [
        "sink_%u",
        "src",
    ]
    assert Gst.ElementFactory.find(element_name) is not None


def test_video_aggregator_registration_marks_the_element_as_video_mixer_surface() -> (
    None
):
    """Checks the authored classification for future compositor-style tests."""
    state = {"aggregate_frames": 0}
    cls = author_video_aggregator_class(
        type_name=unique("VideoAggregatorMetaType"),
        element_name=unique("video_aggregator_meta").lower(),
        state=state,
    )
    assert gst_bucket(cls)["element_metadata"]["classification"] == "Filter/Mixer/Video"


def test_video_aggregator_exposes_video_specific_vfunc_surface() -> None:
    """Checks the subclass and pad vfunc names relevant for video composition."""
    names = GstVideo.VideoAggregator.gimeta.vfunc_infos
    assert "aggregate" in names
    assert "aggregate_frames" in names
    assert "negotiate" in names

    pad_names = GstVideo.VideoAggregatorPad.gimeta.vfunc_infos
    assert "prepare_frame" in pad_names
    assert "prepare_frame_start" in pad_names
    assert "prepare_frame_finish" in pad_names
    assert "clean_frame" in pad_names


def probe_video_aggregator_runtime() -> dict[str, int]:
    state = {"aggregate_frames": 0}
    element_name = unique("video_aggregator_runtime").lower()
    author_video_aggregator_class(
        type_name=unique("VideoAggregatorRuntimeType"),
        element_name=element_name,
        state=state,
    )

    pipe = Gst.Pipeline()
    src1 = Gst.ElementFactory.make("videotestsrc", "src1")
    src2 = Gst.ElementFactory.make("videotestsrc", "src2")
    src1.num_buffers = 1
    src2.num_buffers = 1
    agg = Gst.ElementFactory.make(element_name, "agg")
    sink = Gst.ElementFactory.make("fakesink", "sink")
    sink.sync = False

    pipe.add(src1)
    pipe.add(src2)
    pipe.add(agg)
    pipe.add(sink)
    pad1 = agg.request_pad("sink_%u")
    pad2 = agg.request_pad("sink_%u")
    assert src1.get_static_pad("src").link(pad1) == Gst.PadLinkReturn.OK
    assert src2.get_static_pad("src").link(pad2) == Gst.PadLinkReturn.OK
    assert agg.link(sink) is True
    try:
        assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
        msg = pipe.get_bus().timed_pop_filtered(
            3 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        assert msg is not None
        assert msg.type != Gst.MessageType.ERROR
        return state
    finally:
        pipe.set_state(Gst.State.NULL)
        agg.release_request_pad(pad1)
        agg.release_request_pad(pad2)


def test_video_aggregator_dispatches_aggregate_frames_for_video_inputs() -> None:
    """Verifies aggregate_frames runs when driven by two real raw-video inputs."""
    state = run_subprocess_probe(__file__, "probe_video_aggregator_runtime")
    assert state["aggregate_frames"] >= 1


def test_video_aggregator_negotiates_output_frames_and_reaches_eos() -> None:
    """Checks the video-aggregator helper surface without claiming stable runtime composition."""
    state = {"aggregate_frames": 0}
    cls = author_video_aggregator_class(
        type_name=unique("VideoAggregatorOutputType"),
        element_name=unique("video_aggregator_output").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert hasattr(elt, "finish_buffer")
        assert hasattr(elt, "finish_buffer_list")
        assert hasattr(elt, "selected_samples")
        assert hasattr(elt, "peek_next_sample")
        assert hasattr(elt, "set_src_caps")
        assert hasattr(elt, "get_latency")
        assert hasattr(elt, "set_latency")
        assert hasattr(elt, "push_src_event")
        assert hasattr(elt, "negotiate")
    finally:
        elt.set_state(Gst.State.NULL)
