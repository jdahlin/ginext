# Tests for Gst.Query
#
# SPDX-License-Identifier: LGPL-2.0-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any


class TestQuery:
    def test_new_position_type(self, Gst: Any) -> None:
        q = Gst.Query.new_position(Gst.Format.TIME)
        assert q.type == Gst.QueryType.POSITION

    def test_new_duration_type(self, Gst: Any) -> None:
        q = Gst.Query.new_duration(Gst.Format.TIME)
        assert q.type == Gst.QueryType.DURATION

    def test_new_caps_type(self, Gst: Any) -> None:
        q = Gst.Query.new_caps(None)
        assert q.type == Gst.QueryType.CAPS

    def test_new_latency_type(self, Gst: Any) -> None:
        q = Gst.Query.new_latency()
        assert q.type == Gst.QueryType.LATENCY

    def test_new_seeking_type(self, Gst: Any) -> None:
        q = Gst.Query.new_seeking(Gst.Format.TIME)
        assert q.type == Gst.QueryType.SEEKING

    def test_new_segment_type(self, Gst: Any) -> None:
        q = Gst.Query.new_segment(Gst.Format.TIME)
        assert q.type == Gst.QueryType.SEGMENT

    def test_new_convert_type(self, Gst: Any) -> None:
        q = Gst.Query.new_convert(Gst.Format.TIME, 0, Gst.Format.BYTES)
        assert q.type == Gst.QueryType.CONVERT

    def test_isinstance_query(self, Gst: Any) -> None:
        q = Gst.Query.new_latency()
        assert isinstance(q, Gst.Query)

    def test_parse_position_default(self, Gst: Any) -> None:
        q = Gst.Query.new_position(Gst.Format.TIME)
        fmt, pos = q.parse_position()
        assert fmt == Gst.Format.TIME
        assert pos == -1

    def test_set_and_parse_position(self, Gst: Any) -> None:
        q = Gst.Query.new_position(Gst.Format.TIME)
        q.set_position(Gst.Format.TIME, 3 * Gst.SECOND)
        fmt, pos = q.parse_position()
        assert fmt == Gst.Format.TIME
        assert pos == 3 * Gst.SECOND

    def test_parse_duration_default(self, Gst: Any) -> None:
        q = Gst.Query.new_duration(Gst.Format.TIME)
        fmt, dur = q.parse_duration()
        assert fmt == Gst.Format.TIME
        assert dur == -1

    def test_set_and_parse_duration(self, Gst: Any) -> None:
        q = Gst.Query.new_duration(Gst.Format.TIME)
        q.set_duration(Gst.Format.TIME, 60 * Gst.SECOND)
        fmt, dur = q.parse_duration()
        assert fmt == Gst.Format.TIME
        assert dur == 60 * Gst.SECOND

    def test_set_and_parse_latency(self, Gst: Any) -> None:
        q = Gst.Query.new_latency()
        q.set_latency(True, 10 * Gst.MSECOND, 100 * Gst.MSECOND)
        live, mn, mx = q.parse_latency()
        assert live is True
        assert mn == 10 * Gst.MSECOND
        assert mx == 100 * Gst.MSECOND

    def test_element_query_position(self, Gst: Any) -> None:
        pipe = Gst.parse_launch("fakesrc num-buffers=1 ! fakesink")
        assert pipe.query_position(Gst.Format.TIME) is not None

    def test_element_query_duration(self, Gst: Any) -> None:
        pipe = Gst.parse_launch("fakesrc num-buffers=1 ! fakesink")
        assert pipe.query_duration(Gst.Format.TIME) is not None
