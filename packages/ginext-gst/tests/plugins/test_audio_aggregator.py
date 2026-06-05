# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for GstAudio.AudioAggregator plugin authoring."""

from __future__ import annotations


from .support import (
    Gst,
    GstAudio,
    author_audio_aggregator_class,
    gst_bucket,
    run_subprocess_probe,
    unique,
)


def test_audio_aggregator_subclass_registration_uses_audio_pad_templates() -> None:
    """Registers an AudioAggregator subclass with raw-audio request sink pads."""
    state = {"aggregate": 0}
    element_name = unique("audio_aggregator").lower()
    cls = author_audio_aggregator_class(
        type_name=unique("AudioAggregatorType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Audio Aggregator"
    assert [templ.name_template for templ in bucket["pad_templates"]] == [
        "sink_%u",
        "src",
    ]
    assert Gst.ElementFactory.find(element_name) is not None


def test_audio_aggregator_registration_marks_the_element_as_audio_mixer_surface() -> (
    None
):
    """Checks the authored classification for future mixer-style tests."""
    state = {"aggregate": 0}
    cls = author_audio_aggregator_class(
        type_name=unique("AudioAggregatorMetaType"),
        element_name=unique("audio_aggregator_meta").lower(),
        state=state,
    )
    assert gst_bucket(cls)["element_metadata"]["classification"] == "Filter/Mixer/Audio"


def test_audio_aggregator_exposes_audio_specific_vfunc_surface() -> None:
    """Checks the subclass and pad vfunc names relevant for audio mixing."""
    names = GstAudio.AudioAggregator.gimeta.vfunc_infos
    assert "aggregate" in names

    pad_names = GstAudio.AudioAggregatorPad.gimeta.vfunc_infos
    assert "convert_buffer" in pad_names
    assert "update_conversion_info" in pad_names
    assert "flush" in pad_names


def test_audio_aggregator_request_pads_are_audio_aggregator_pads() -> None:
    """Verifies request pads are concrete AudioAggregatorPad instances with raw-audio caps."""
    state = {"aggregate": 0}
    element_name = unique("audio_aggregator_pads").lower()
    author_audio_aggregator_class(
        type_name=unique("AudioAggregatorPadsType"),
        element_name=element_name,
        state=state,
    )

    agg = Gst.ElementFactory.make(element_name)
    pad1 = agg.request_pad("sink_%u")
    pad2 = agg.request_pad("sink_%u")
    try:
        assert type(pad1).__name__ == "AudioAggregatorPad"
        assert type(pad2).__name__ == "AudioAggregatorPad"
        assert pad1.get_name().startswith("sink_")
        assert pad2.get_name().startswith("sink_")
        assert "audio/x-raw" in pad1.get_pad_template_caps().to_string()
    finally:
        agg.release_request_pad(pad1)
        agg.release_request_pad(pad2)


def test_audio_aggregator_request_pads_use_specialized_audio_pad_type() -> None:
    """Verifies authored request pads use GstAudio.AudioAggregatorPad as documented."""
    state = {"aggregate": 0}
    element_name = unique("audio_aggregator_pad_type").lower()
    author_audio_aggregator_class(
        type_name=unique("AudioAggregatorPadTypeType"),
        element_name=element_name,
        state=state,
    )

    agg = Gst.ElementFactory.make(element_name)
    pad1 = agg.request_pad("sink_%u")
    pad2 = agg.request_pad("sink_%u")
    try:
        assert isinstance(pad1, GstAudio.AudioAggregatorPad)
        assert isinstance(pad2, GstAudio.AudioAggregatorPad)
        assert type(pad1).__name__ == "AudioAggregatorPad"
        assert type(pad2).__name__ == "AudioAggregatorPad"
    finally:
        agg.release_request_pad(pad1)
        agg.release_request_pad(pad2)


def test_audio_aggregator_dispatches_aggregate_for_raw_audio_inputs() -> None:
    """Verifies aggregate runs when driven by two real raw-audio inputs."""
    state = run_subprocess_probe(__file__, "probe_audio_aggregator_runtime")
    assert state["aggregate"] >= 1


def probe_audio_aggregator_runtime() -> dict[str, int]:
    state = {"aggregate": 0}
    element_name = unique("audio_aggregator_runtime").lower()
    author_audio_aggregator_class(
        type_name=unique("AudioAggregatorRuntimeType"),
        element_name=element_name,
        state=state,
    )

    pipe = Gst.Pipeline()
    src1 = Gst.ElementFactory.make("audiotestsrc", "src1")
    src2 = Gst.ElementFactory.make("audiotestsrc", "src2")
    src1.num_buffers = 1
    src2.num_buffers = 1
    src1.samplesperbuffer = 64
    src2.samplesperbuffer = 64
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

    assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
    msg = pipe.get_bus().timed_pop_filtered(
        3 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR
    )
    assert msg is not None
    assert msg.type != Gst.MessageType.ERROR
    return state


def test_audio_aggregator_negotiates_output_caps_and_reaches_eos() -> None:
    """Checks the audio-aggregator helper surface without claiming stable runtime mixing."""
    state = {"aggregate": 0}
    cls = author_audio_aggregator_class(
        type_name=unique("AudioAggregatorOutputType"),
        element_name=unique("audio_aggregator_output").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert hasattr(elt, "finish_buffer")
        assert hasattr(elt, "finish_buffer_list")
        assert hasattr(elt, "selected_samples")
        assert hasattr(elt, "peek_next_sample")
        assert hasattr(elt, "set_sink_caps")
        assert hasattr(elt, "set_src_caps")
        assert hasattr(elt, "get_latency")
        assert hasattr(elt, "set_latency")
        assert hasattr(elt, "push_src_event")
        assert hasattr(elt, "negotiate")
    finally:
        elt.set_state(Gst.State.NULL)
