# Tests for Gst.MiniObject-style records and shared copy/writability semantics.
#
# SPDX-License-Identifier: LGPL-2.0-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any


def _message(Gst: Any) -> Any:
    src = Gst.ElementFactory.make("fakesrc", "miniobject-src")
    return Gst.Message.new_eos(src)


class TestMiniObjectSemantics:
    def test_caps_copy_returns_caps(self, Gst: Any) -> None:
        caps = Gst.Caps("video/x-raw")
        copied = caps.copy()
        assert isinstance(copied, Gst.Caps)
        assert copied is not caps
        assert copied.to_string() == caps.to_string()

    def test_event_copy_preserves_type(self, Gst: Any) -> None:
        event = Gst.Event.new_eos()
        copied = event.copy()
        assert isinstance(copied, Gst.Event)
        assert copied is not event
        assert copied.type == event.type

    def test_message_copy_preserves_type_and_src(self, Gst: Any) -> None:
        message = _message(Gst)
        copied = message.copy()
        assert isinstance(copied, Gst.Message)
        assert copied is not message
        assert copied.type == message.type
        assert copied.src == message.src

    def test_query_copy_preserves_type(self, Gst: Any) -> None:
        query = Gst.Query.new_latency()
        query.set_latency(True, 10 * Gst.MSECOND, 100 * Gst.MSECOND)
        copied = query.copy()
        assert isinstance(copied, Gst.Query)
        assert copied is not query
        assert copied.type == query.type
        assert copied.parse_latency() == query.parse_latency()

    def test_tag_list_copy_preserves_items(self, Gst: Any) -> None:
        tags = Gst.TagList()
        tags[Gst.TAG_TITLE] = "title"
        copied = tags.copy()
        assert isinstance(copied, Gst.TagList)
        assert copied is not tags
        assert len(copied) == 1
        assert copied[0] == "title"

    def test_buffer_list_copy_returns_same_wrapper_type(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, Gst.Buffer.new_wrapped(b"a"))
        copied = buffer_list.copy()
        assert isinstance(copied, Gst.BufferList)
        assert copied is not buffer_list
        assert copied.length() == buffer_list.length()

    def test_sample_copy_returns_same_wrapper_type(self, Gst: Any) -> None:
        sample = Gst.Sample.new(
            Gst.Buffer.new_wrapped(b"xyz"),
            Gst.Caps("video/x-raw"),
            None,
            None,
        )
        copied = sample.copy()
        assert isinstance(copied, Gst.Sample)
        assert copied is not sample
        assert copied.get_buffer().get_size() == sample.get_buffer().get_size()
        assert copied.get_caps().to_string() == sample.get_caps().to_string()

    def test_caps_is_writable(self, Gst: Any) -> None:
        caps = Gst.Caps("video/x-raw")
        assert caps.is_writable() is True

    def test_event_is_writable(self, Gst: Any) -> None:
        assert Gst.Event.new_eos().is_writable() is True

    def test_message_is_writable(self, Gst: Any) -> None:
        assert _message(Gst).is_writable() is True

    def test_query_is_writable(self, Gst: Any) -> None:
        assert Gst.Query.new_latency().is_writable() is True

    def test_tag_list_is_writable(self, Gst: Any) -> None:
        assert Gst.TagList().is_writable() is True
