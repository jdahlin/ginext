# Ported from gst-python testsuite and ginext backlog
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest

from ginext.namespace import Namespace


def _make_buffer(Gst: Namespace, payload: bytes) -> object:
    buf = Gst.Buffer.new_allocate(None, len(payload), None)
    buf.fill(0, payload)
    return buf


class TestBuffer:
    def test_new_allocate(self, Gst: Namespace) -> None:
        buf = Gst.Buffer.new_allocate(None, 16, None)
        assert buf is not None
        assert buf.get_size() == 16

    def test_new_wrapped(self, Gst: Namespace) -> None:
        buf = Gst.Buffer.new_wrapped(b"hello")
        assert buf is not None
        assert buf.get_size() == 5

    def test_fill_and_extract_dup(self, Gst: Namespace) -> None:
        payload = b"hello world wxyz"
        buf = _make_buffer(Gst, payload)
        data = getattr(buf, "extract_dup")(0, getattr(buf, "get_size")())
        assert data == payload

    def test_pts_default(self, Gst: Namespace) -> None:
        buf = Gst.Buffer.new_allocate(None, 4, None)
        assert buf.pts == Gst.CLOCK_TIME_NONE

    def test_dts_default(self, Gst: Namespace) -> None:
        buf = Gst.Buffer.new_allocate(None, 4, None)
        assert buf.dts == Gst.CLOCK_TIME_NONE

    def test_duration_default(self, Gst: Namespace) -> None:
        buf = Gst.Buffer.new_allocate(None, 4, None)
        assert buf.duration == Gst.CLOCK_TIME_NONE

    def test_set_pts(self, Gst: Namespace) -> None:
        buf = Gst.Buffer.new_allocate(None, 4, None)
        buf.pts = Gst.SECOND
        assert buf.pts == Gst.SECOND

    def test_map_returns_success_and_info(self, Gst: Namespace) -> None:
        payload = b"hello world wxyz"
        buf = _make_buffer(Gst, payload)
        success, info = getattr(buf, "map")(Gst.MapFlags.READ)
        assert success
        assert info is not None
        getattr(buf, "unmap")(info)

    def test_map_size(self, Gst: Namespace) -> None:
        payload = b"x" * 64
        buf = _make_buffer(Gst, payload)
        success, info = getattr(buf, "map")(Gst.MapFlags.READ)
        assert success
        assert getattr(info, "size") == len(payload)
        getattr(buf, "unmap")(info)

    def test_map_data_bytes(self, Gst: Namespace) -> None:
        """map() overlay populates info.data via extract_dup."""
        payload = b"hello world wxyz"
        buf = _make_buffer(Gst, payload)
        success, info = getattr(buf, "map")(Gst.MapFlags.READ)
        assert success
        assert hasattr(info, "data"), f"MapInfo missing .data: {info!r}"
        assert isinstance(getattr(info, "data"), (bytes, bytearray, memoryview))
        assert bytes(getattr(info, "data")) == payload
        getattr(buf, "unmap")(info)

    def test_map_data_length_matches_size(self, Gst: Namespace) -> None:
        payload = b"x" * 64
        buf = _make_buffer(Gst, payload)
        success, info = getattr(buf, "map")(Gst.MapFlags.READ)
        assert success
        assert len(getattr(info, "data")) == getattr(info, "size")
        getattr(buf, "unmap")(info)

    def test_map_empty_buffer(self, Gst: Namespace) -> None:
        payload = b"\x00"
        buf = _make_buffer(Gst, payload)
        success, info = getattr(buf, "map")(Gst.MapFlags.READ)
        assert success
        assert getattr(info, "size") == 1
        assert bytes(getattr(info, "data")) == payload
        getattr(buf, "unmap")(info)

    def test_map_overlay_loads_on_class_access(self, Gst: Namespace) -> None:
        """Buffer.map should be the overlay-patched version."""
        # The overlay replaces map so info.data is populated; check the
        # method is callable and returns the ginext-augmented result.
        buf = Gst.Buffer.new_wrapped(b"test")
        success, info = buf.map(Gst.MapFlags.READ)
        assert success
        assert hasattr(info, "data")
        buf.unmap(info)


class TestBufferClock:
    """GstClockID is a gpointer — it must round-trip as a Python int.

    gnome-music's gstplayer does `if self._clock_id > 0:` on the return
    value of new_periodic_id, so returning None would crash.
    """

    def test_new_periodic_id_returns_int(self, Gst: Namespace) -> None:
        clock = Gst.SystemClock.obtain()
        cid = clock.new_periodic_id(clock.get_time(), 1 * Gst.SECOND)
        assert isinstance(cid, int)
        assert cid > 0
        clock.id_unschedule(cid)

    def test_new_single_shot_id_returns_int(self, Gst: Namespace) -> None:
        clock = Gst.SystemClock.obtain()
        cid = clock.new_single_shot_id(clock.get_time() + Gst.SECOND)
        assert isinstance(cid, int)
        assert cid > 0
        clock.id_unschedule(cid)

    def test_gpointer_arg_accepts_none_as_null(
        self, Gst: Namespace, capfd: pytest.CaptureFixture[str]
    ) -> None:
        """None passes through as NULL; gst_clock_id_unschedule is a no-op."""
        clock = Gst.SystemClock.obtain()
        clock.id_unschedule(None)
        capfd.readouterr()

    def test_gpointer_arg_accepts_non_int(
        self, Gst: Namespace, capfd: pytest.CaptureFixture[str]
    ) -> None:
        """Non-int / non-None gpointer args are silently sent as NULL."""
        clock = Gst.SystemClock.obtain()
        clock.id_unschedule(object())
        capfd.readouterr()
