"""Tests for GstAudio.AudioEncoder plugin authoring."""

from __future__ import annotations

from .support import Gst, author_audio_encoder_class, gst_bucket, unique


def test_audio_encoder_subclass_registration_records_encoder_metadata() -> None:
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    element_name = unique("audio_encoder").lower()
    cls = author_audio_encoder_class(
        type_name=unique("AudioEncoderType"),
        element_name=element_name,
        state=state,
    )
    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Audio Encoder"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_audio_encoder_dispatches_set_format_and_handle_frame_vfuncs() -> None:
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_audio_encoder_class(
        type_name=unique("AudioEncoderVfuncType"),
        element_name=unique("audio_encoder_vfunc").lower(),
        state=state,
    )

    names = cls.gimeta.vfunc_infos
    assert "start" in names
    assert "stop" in names
    assert "set_format" in names
    assert "handle_frame" in names
    assert "flush" in names
    assert "pre_push" in names


def test_audio_encoder_can_allocate_output_and_finish_encoded_frames() -> None:
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_audio_encoder_class(
        type_name=unique("AudioEncoderHelperType"),
        element_name=unique("audio_encoder_helpers").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.get_drainable() is True
        assert elt.set_drainable(True) is None
        assert elt.get_frame_max() == 0
        assert elt.set_frame_max(7) is None
        assert elt.get_frame_samples_min() == 0
        assert elt.set_frame_samples_min(1) is None
        assert elt.get_frame_samples_max() == 0
        assert elt.set_frame_samples_max(9) is None
        assert hasattr(elt, "finish_frame")
        assert hasattr(elt, "set_output_format")
    finally:
        elt.set_state(Gst.State.NULL)


def test_audio_encoder_can_drop_or_flush_pending_input_cleanly() -> None:
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_audio_encoder_class(
        type_name=unique("AudioEncoderDrainType"),
        element_name=unique("audio_encoder_drain").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.set_state(Gst.State.READY) != Gst.StateChangeReturn.FAILURE
        assert "flush" in cls.gimeta.vfunc_infos
        assert hasattr(elt, "finish_frame")
        assert hasattr(elt, "negotiate")
    finally:
        elt.set_state(Gst.State.NULL)
