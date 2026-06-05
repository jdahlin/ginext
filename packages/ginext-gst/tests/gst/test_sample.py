# Tests for Gst.Sample
#
# SPDX-License-Identifier: LGPL-2.0-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any


def _sample(Gst: Any, payload: bytes = b"xyz") -> Any:
    return Gst.Sample.new(
        Gst.Buffer.new_wrapped(payload),
        Gst.Caps("video/x-raw"),
        None,
        None,
    )


class TestSample:
    def test_new(self, Gst: Any) -> None:
        sample = _sample(Gst)
        assert isinstance(sample, Gst.Sample)

    def test_get_buffer(self, Gst: Any) -> None:
        sample = _sample(Gst, b"abcd")
        buffer = sample.get_buffer()
        assert isinstance(buffer, Gst.Buffer)
        assert buffer.get_size() == 4

    def test_get_caps(self, Gst: Any) -> None:
        sample = _sample(Gst)
        caps = sample.get_caps()
        assert isinstance(caps, Gst.Caps)
        assert caps.to_string() == "video/x-raw"

    def test_get_info_defaults_none(self, Gst: Any) -> None:
        sample = _sample(Gst)
        assert sample.get_info() is None

    def test_get_segment(self, Gst: Any) -> None:
        sample = _sample(Gst)
        segment = sample.get_segment()
        assert isinstance(segment, Gst.Segment)
        assert segment.format == Gst.Format.TIME

    def test_set_buffer(self, Gst: Any) -> None:
        sample = _sample(Gst)
        sample = sample.make_writable()
        sample.set_buffer(Gst.Buffer.new_wrapped(b"pq"))
        assert sample.get_buffer().get_size() == 2

    def test_set_caps(self, Gst: Any) -> None:
        sample = _sample(Gst)
        sample = sample.make_writable()
        sample.set_caps(Gst.Caps("audio/x-raw"))
        assert sample.get_caps().to_string() == "audio/x-raw"

    def test_set_segment(self, Gst: Any) -> None:
        sample = _sample(Gst)
        sample = sample.make_writable()
        segment = Gst.Segment()
        segment.init(Gst.Format.TIME)
        sample.set_segment(segment)
        assert sample.get_segment().format == Gst.Format.TIME

    def test_copy_preserves_buffer_and_caps(self, Gst: Any) -> None:
        sample = _sample(Gst, b"hello")
        copied = sample.copy()
        assert copied is not sample
        assert copied.get_buffer().get_size() == 5
        assert copied.get_caps().to_string() == "video/x-raw"

    def test_make_writable_returns_sample(self, Gst: Any) -> None:
        sample = _sample(Gst)
        writable = sample.make_writable()
        assert isinstance(writable, Gst.Sample)

    def test_repr(self, Gst: Any) -> None:
        sample = _sample(Gst, b"xyz")
        assert repr(sample) == "<Gst.Sample caps='video/x-raw' buffer_size=3>"
