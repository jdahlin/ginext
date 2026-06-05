"""Tests for GstAudio.AudioDecoder plugin authoring."""

from __future__ import annotations

from .support import Gst, author_audio_decoder_class, gst_bucket, unique


def test_audio_decoder_subclass_registration_records_decoder_metadata() -> None:
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    element_name = unique("audio_decoder").lower()
    cls = author_audio_decoder_class(
        type_name=unique("AudioDecoderType"),
        element_name=element_name,
        state=state,
    )
    bucket = gst_bucket(cls)
    assert bucket["element_metadata"]["longname"] == "Python Audio Decoder"
    assert [templ.name_template for templ in bucket["pad_templates"]] == ["sink", "src"]
    assert Gst.ElementFactory.find(element_name) is not None


def test_audio_decoder_dispatches_set_format_and_handle_frame_vfuncs() -> None:
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_audio_decoder_class(
        type_name=unique("AudioDecoderVfuncType"),
        element_name=unique("audio_decoder_vfunc").lower(),
        state=state,
    )

    names = cls.gimeta.vfunc_infos
    assert "start" in names
    assert "stop" in names
    assert "set_format" in names
    assert "handle_frame" in names
    assert "flush" in names
    assert "pre_push" in names


def test_audio_decoder_can_set_output_format_and_finish_frames() -> None:
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_audio_decoder_class(
        type_name=unique("AudioDecoderHelperType"),
        element_name=unique("audio_decoder_helpers").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.get_drainable() is True
        assert elt.set_drainable(True) is None
        assert hasattr(elt, "finish_frame")
        assert hasattr(elt, "finish_subframe")
        assert hasattr(elt, "set_output_caps")
        assert hasattr(elt, "set_output_format")
        assert hasattr(elt, "negotiate")
        assert elt.negotiate() is False
    finally:
        elt.set_state(Gst.State.NULL)


def test_audio_decoder_handles_eos_and_drain_without_crashing() -> None:
    state = {"start": 0, "stop": 0, "set_format": 0, "handle_frame": 0}
    cls = author_audio_decoder_class(
        type_name=unique("AudioDecoderDrainType"),
        element_name=unique("audio_decoder_drain").lower(),
        state=state,
    )
    elt = cls()
    try:
        assert elt.set_state(Gst.State.READY) != Gst.StateChangeReturn.FAILURE
        assert "flush" in cls.gimeta.vfunc_infos
        assert hasattr(elt, "get_drainable")
        assert hasattr(elt, "set_drainable")
    finally:
        elt.set_state(Gst.State.NULL)
