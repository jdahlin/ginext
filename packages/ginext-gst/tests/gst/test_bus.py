# Tests for Gst.Bus and Gst.Message
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import types


# ---------------------------------------------------------------------------
# TestBus
# ---------------------------------------------------------------------------


class TestBus:
    def test_get_bus(self, Gst: types.ModuleType) -> None:
        pipe = Gst.Pipeline()
        bus = pipe.get_bus()
        assert bus is not None
        assert isinstance(bus, Gst.Bus)

    def test_timed_pop_empty(self, Gst: types.ModuleType) -> None:
        pipe = Gst.Pipeline()
        bus = pipe.get_bus()
        msg = bus.timed_pop(0)
        assert msg is None

    def test_timed_pop_filtered_empty(self, Gst: types.ModuleType) -> None:
        pipe = Gst.Pipeline()
        bus = pipe.get_bus()
        msg = bus.timed_pop_filtered(0, Gst.MessageType.ANY)
        assert msg is None

    def test_post_and_pop(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pipe = Gst.Pipeline()
        pipe.add(src)
        bus = pipe.get_bus()
        msg = Gst.Message.new_eos(src)
        assert bus.post(msg)
        received = bus.timed_pop(0)
        assert received is not None
        assert received.type == Gst.MessageType.EOS

    def test_post_filtered_matches_type(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pipe = Gst.Pipeline()
        pipe.add(src)
        bus = pipe.get_bus()
        bus.post(Gst.Message.new_eos(src))
        received = bus.timed_pop_filtered(0, Gst.MessageType.EOS)
        assert received is not None
        assert received.type == Gst.MessageType.EOS

    def test_post_filtered_no_match(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        pipe = Gst.Pipeline()
        pipe.add(src)
        bus = pipe.get_bus()
        bus.post(Gst.Message.new_eos(src))
        received = bus.timed_pop_filtered(0, Gst.MessageType.ERROR)
        assert received is None

    def test_isinstance_bus(self, Gst: types.ModuleType) -> None:
        pipe = Gst.Pipeline()
        bus = pipe.get_bus()
        assert isinstance(bus, Gst.Bus)

    def test_isinstance_object(self, Gst: types.ModuleType) -> None:
        pipe = Gst.Pipeline()
        bus = pipe.get_bus()
        assert isinstance(bus, Gst.Object)


# ---------------------------------------------------------------------------
# TestMessage
# ---------------------------------------------------------------------------


class TestMessage:
    def test_new_eos_type(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        msg = Gst.Message.new_eos(src)
        assert msg.type == Gst.MessageType.EOS

    def test_new_state_changed_type(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        msg = Gst.Message.new_state_changed(
            src, Gst.State.NULL, Gst.State.READY, Gst.State.NULL
        )
        assert msg.type == Gst.MessageType.STATE_CHANGED

    def test_new_buffering_type(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        msg = Gst.Message.new_buffering(src, 50)
        assert msg.type == Gst.MessageType.BUFFERING

    def test_new_latency_type(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        msg = Gst.Message.new_latency(src)
        assert msg.type == Gst.MessageType.LATENCY

    def test_src_element(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", "testsrc")
        msg = Gst.Message.new_eos(src)
        assert msg.src == src

    def test_parse_state_changed(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        msg = Gst.Message.new_state_changed(
            src, Gst.State.NULL, Gst.State.READY, Gst.State.NULL
        )
        old, new, pending = msg.parse_state_changed()
        assert old == Gst.State.NULL
        assert new == Gst.State.READY
        assert pending == Gst.State.NULL

    def test_isinstance_message(self, Gst: types.ModuleType) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        msg = Gst.Message.new_eos(src)
        assert isinstance(msg, Gst.Message)
