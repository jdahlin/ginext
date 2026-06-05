# Tests for Gst.Element, Gst.Pad, and Gst.Segment
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext.namespace import Namespace


# ---------------------------------------------------------------------------
# TestElement
# ---------------------------------------------------------------------------


class TestElement:
    def test_link_many(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        sink = Gst.ElementFactory.make("fakesink", None)
        pipe = Gst.Pipeline()
        pipe.add(src, sink)
        Gst.Element.link_many(src, sink)

    def test_link_many_fail(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        sink = Gst.ElementFactory.make("fakesink", None)
        src2 = Gst.ElementFactory.make("fakesrc", None)
        pipe = Gst.Pipeline()
        pipe.add(src, sink, src2)
        with pytest.raises(Gst.LinkError):
            Gst.Element.link_many(src, sink, src2)

    def test_get_static_pad(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pad = src.get_static_pad("src")
        assert pad is not None

    def test_get_name_auto(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        name = src.get_name()
        assert name is not None
        assert "fakesrc" in name

    def test_get_name_explicit(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", "mysrc")
        assert src.get_name() == "mysrc"

    def test_set_get_property(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        src.num_buffers = 7
        assert src.get_property("num-buffers") == 7

    def test_get_factory_name(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        factory = src.get_factory()
        assert factory is not None
        assert factory.get_name() == "fakesrc"

    def test_isinstance_element(self, Gst: Namespace) -> None:
        elem = Gst.ElementFactory.make("fakesrc", None)
        assert isinstance(elem, Gst.Element)

    def test_isinstance_object(self, Gst: Namespace) -> None:
        elem = Gst.ElementFactory.make("fakesrc", None)
        assert isinstance(elem, Gst.Object)

    def test_n_pads(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pads = list(src.iterate_pads())
        assert len(pads) == 1

    def test_get_bus_none_when_not_in_pipeline(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        assert src.get_bus() is None

    def test_state_default_null(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        ret, state, pending = src.get_state(0)
        assert state == Gst.State.NULL

    def test_set_state_ready(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        ret = src.set_state(Gst.State.READY)
        assert ret != Gst.StateChangeReturn.FAILURE
        src.set_state(Gst.State.NULL)


# ---------------------------------------------------------------------------
# TestPad
# ---------------------------------------------------------------------------


class TestPad:
    def test_direction_src(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pad = src.get_static_pad("src")
        assert pad.get_direction() == Gst.PadDirection.SRC

    def test_direction_sink(self, Gst: Namespace) -> None:
        sink = Gst.ElementFactory.make("fakesink", None)
        pad = sink.get_static_pad("sink")
        assert pad.get_direction() == Gst.PadDirection.SINK

    def test_name_src(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pad = src.get_static_pad("src")
        assert pad.get_name() == "src"

    def test_name_sink(self, Gst: Namespace) -> None:
        sink = Gst.ElementFactory.make("fakesink", None)
        pad = sink.get_static_pad("sink")
        assert pad.get_name() == "sink"

    def test_not_linked_initially(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pad = src.get_static_pad("src")
        assert not pad.is_linked()

    def test_linked_after_link(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        sink = Gst.ElementFactory.make("fakesink", None)
        pipe = Gst.Pipeline()
        pipe.add(src, sink)
        src.link(sink)
        assert src.get_static_pad("src").is_linked()
        assert sink.get_static_pad("sink").is_linked()

    def test_get_parent_element(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pad = src.get_static_pad("src")
        assert pad.get_parent_element() == src

    def test_query_caps_returns_caps(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pad = src.get_static_pad("src")
        caps = pad.query_caps(None)
        assert caps is not None
        assert isinstance(caps, Gst.Caps)

    def test_isinstance_pad(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pad = src.get_static_pad("src")
        assert isinstance(pad, Gst.Pad)

    def test_isinstance_object(self, Gst: Namespace) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pad = src.get_static_pad("src")
        assert isinstance(pad, Gst.Object)


# ---------------------------------------------------------------------------
# TestSegment
# ---------------------------------------------------------------------------


class TestSegment:
    def test_new(self, Gst: Namespace) -> None:
        seg = Gst.Segment()
        assert seg is not None

    def test_init_time_format(self, Gst: Namespace) -> None:
        seg = Gst.Segment()
        seg.init(Gst.Format.TIME)
        assert seg.format == Gst.Format.TIME

    def test_start_default(self, Gst: Namespace) -> None:
        seg = Gst.Segment()
        seg.init(Gst.Format.TIME)
        assert seg.start == 0

    def test_stop_default(self, Gst: Namespace) -> None:
        seg = Gst.Segment()
        seg.init(Gst.Format.TIME)
        assert seg.stop == Gst.CLOCK_TIME_NONE

    def test_rate_default(self, Gst: Namespace) -> None:
        seg = Gst.Segment()
        seg.init(Gst.Format.TIME)
        assert seg.rate == 1.0

    def test_copy(self, Gst: Namespace) -> None:
        seg = Gst.Segment()
        seg.init(Gst.Format.TIME)
        copy = seg.copy()
        assert copy is not None
        assert copy.format == Gst.Format.TIME
        assert copy is not seg
