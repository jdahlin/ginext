# Tests for Gst.Event
#
# SPDX-License-Identifier: LGPL-2.0-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any


class TestEvent:
    def test_new_eos_type(self, Gst: Any) -> None:
        event = Gst.Event.new_eos()
        assert event.type == Gst.EventType.EOS

    def test_new_flush_start_type(self, Gst: Any) -> None:
        event = Gst.Event.new_flush_start()
        assert event.type == Gst.EventType.FLUSH_START

    def test_new_flush_stop_type(self, Gst: Any) -> None:
        event = Gst.Event.new_flush_stop(True)
        assert event.type == Gst.EventType.FLUSH_STOP

    def test_new_gap_type(self, Gst: Any) -> None:
        event = Gst.Event.new_gap(0, Gst.SECOND)
        assert event.type == Gst.EventType.GAP

    def test_new_seek_type(self, Gst: Any) -> None:
        event = Gst.Event.new_seek(
            1.0,
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH,
            Gst.SeekType.SET,
            0,
            Gst.SeekType.NONE,
            -1,
        )
        assert event.type == Gst.EventType.SEEK

    def test_isinstance_event(self, Gst: Any) -> None:
        event = Gst.Event.new_eos()
        assert isinstance(event, Gst.Event)

    def test_eos_is_downstream(self, Gst: Any) -> None:
        assert Gst.EventType.EOS & Gst.EventTypeFlags.DOWNSTREAM

    def test_flush_start_is_upstream_and_downstream(self, Gst: Any) -> None:
        flags = Gst.EventTypeFlags.UPSTREAM | Gst.EventTypeFlags.DOWNSTREAM
        assert Gst.EventType.FLUSH_START & flags

    def test_parse_seek(self, Gst: Any) -> None:
        event = Gst.Event.new_seek(
            1.0,
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH,
            Gst.SeekType.SET,
            5 * Gst.SECOND,
            Gst.SeekType.NONE,
            -1,
        )
        rate, fmt, flags, start_type, start, stop_type, stop = event.parse_seek()
        assert rate == 1.0
        assert fmt == Gst.Format.TIME
        assert flags == Gst.SeekFlags.FLUSH
        assert start_type == Gst.SeekType.SET
        assert start == 5 * Gst.SECOND

    def test_parse_gap(self, Gst: Any) -> None:
        event = Gst.Event.new_gap(2 * Gst.SECOND, Gst.SECOND)
        timestamp, duration = event.parse_gap()
        assert timestamp == 2 * Gst.SECOND
        assert duration == Gst.SECOND

    def test_new_caps_type(self, Gst: Any) -> None:
        caps = Gst.Caps("video/x-raw")
        event = Gst.Event.new_caps(caps)
        assert event.type == Gst.EventType.CAPS

    def test_parse_caps(self, Gst: Any) -> None:
        caps = Gst.Caps("video/x-raw")
        event = Gst.Event.new_caps(caps)
        parsed = event.parse_caps()
        assert parsed is not None
        assert parsed.to_string() == caps.to_string()

    def test_new_tag_type(self, Gst: Any) -> None:
        tl = Gst.TagList()
        tl[Gst.TAG_TITLE] = "test"
        event = Gst.Event.new_tag(tl)
        assert event.type == Gst.EventType.TAG

    def test_new_reconfigure_type(self, Gst: Any) -> None:
        event = Gst.Event.new_reconfigure()
        assert event.type == Gst.EventType.RECONFIGURE
