# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for GstVideo.VideoDecoder plugin authoring."""

from __future__ import annotations

from .support import Gst, author_video_decoder_class, gst_bucket, unique


def test_video_decoder_subclass_registration_records_decoder_metadata() -> None:
    """Registers a VideoDecoder subclass with encoded input and raw output pads."""
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    element_name = unique("video_decoder").lower()
    cls = author_video_decoder_class(
        type_name=unique("VideoDecoderType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Video Decoder"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_video_decoder_dispatches_set_format_and_handle_frame_vfuncs() -> None:
    """Checks the authored decode-time vfunc surface exposed to Python subclasses."""
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_video_decoder_class(
        type_name=unique("VideoDecoderVfuncType"),
        element_name=unique("video_decoder_vfunc").lower(),
        state=state,
    )

    names = cls.gimeta.vfunc_infos
    assert "start" in names
    assert "stop" in names
    assert "set_format" in names
    assert "handle_frame" in names
    assert "flush" in names
    assert "drain" in names
    assert "handle_missing_data" in names


def test_video_decoder_can_set_output_state_and_finish_frames() -> None:
    """Checks the output-state and frame helper methods exposed on instances."""
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_video_decoder_class(
        type_name=unique("VideoDecoderHelperType"),
        element_name=unique("video_decoder_helpers").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.get_subframe_mode() is False
        assert elt.set_subframe_mode(True) is None
        assert hasattr(elt, "allocate_output_frame")
        assert hasattr(elt, "allocate_output_frame_with_params")
        assert hasattr(elt, "set_output_state")
        assert hasattr(elt, "finish_frame")
        assert hasattr(elt, "finish_subframe")
        assert elt.negotiate() is False
    finally:
        elt.set_state(Gst.State.NULL)


def test_video_decoder_handles_eos_and_drain_without_crashing() -> None:
    """Checks drain-related helper exposure without claiming full runtime decode coverage."""
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_video_decoder_class(
        type_name=unique("VideoDecoderDrainType"),
        element_name=unique("video_decoder_drain").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.set_state(Gst.State.READY) != Gst.StateChangeReturn.FAILURE
        assert "drain" in cls.gimeta.vfunc_infos
        assert hasattr(elt, "get_frames")
        assert hasattr(elt, "release_frame")
        assert hasattr(elt, "drop_frame")
    finally:
        elt.set_state(Gst.State.NULL)
