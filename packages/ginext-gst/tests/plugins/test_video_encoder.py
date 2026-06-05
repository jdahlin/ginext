# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for GstVideo.VideoEncoder plugin authoring."""

from __future__ import annotations

from .support import Gst, author_video_encoder_class, gst_bucket, unique


def test_video_encoder_subclass_registration_records_encoder_metadata() -> None:
    """Registers a VideoEncoder subclass with raw input and encoded output pads."""
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    element_name = unique("video_encoder").lower()
    cls = author_video_encoder_class(
        type_name=unique("VideoEncoderType"),
        element_name=element_name,
        state=state,
    )

    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Video Encoder"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_video_encoder_dispatches_set_format_and_handle_frame_vfuncs() -> None:
    """Checks the authored encode-time vfunc surface exposed to Python subclasses."""
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_video_encoder_class(
        type_name=unique("VideoEncoderVfuncType"),
        element_name=unique("video_encoder_vfunc").lower(),
        state=state,
    )

    names = cls.gimeta.vfunc_infos
    assert "start" in names
    assert "stop" in names
    assert "set_format" in names
    assert "handle_frame" in names
    assert "flush" in names
    assert "pre_push" in names


def test_video_encoder_can_allocate_output_and_finish_encoded_frames() -> None:
    """Checks the output-state and frame helper methods exposed on instances."""
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_video_encoder_class(
        type_name=unique("VideoEncoderHelperType"),
        element_name=unique("video_encoder_helpers").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert hasattr(elt, "allocate_output_frame")
        assert hasattr(elt, "set_output_state")
        assert hasattr(elt, "finish_frame")
        assert hasattr(elt, "finish_subframe")
        assert hasattr(elt, "drop_frame")
        assert elt.negotiate() is False
    finally:
        elt.set_state(Gst.State.NULL)


def test_video_encoder_can_drop_or_flush_pending_input_cleanly() -> None:
    """Checks flush/drop-related helper exposure without claiming full runtime encode coverage."""
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_video_encoder_class(
        type_name=unique("VideoEncoderDrainType"),
        element_name=unique("video_encoder_drain").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.set_state(Gst.State.READY) != Gst.StateChangeReturn.FAILURE
        assert "flush" in cls.gimeta.vfunc_infos
        assert hasattr(elt, "get_frames")
        assert hasattr(elt, "release_frame")
    finally:
        elt.set_state(Gst.State.NULL)
