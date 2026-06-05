# Tests for Gst.BufferList
#
# SPDX-License-Identifier: LGPL-2.0-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any


def _buffer(Gst: Any, payload: bytes) -> Any:
    return Gst.Buffer.new_wrapped(payload)


class TestBufferList:
    def test_new_is_empty(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        assert isinstance(buffer_list, Gst.BufferList)
        assert buffer_list.length() == 0

    def test_insert_and_get(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        first = _buffer(Gst, b"a")
        second = _buffer(Gst, b"bc")
        buffer_list.insert(-1, first)
        buffer_list.insert(-1, second)
        assert buffer_list.length() == 2
        assert buffer_list.get(0).extract_dup(0, 1) == b"a"
        assert buffer_list.get(1).extract_dup(0, 2) == b"bc"

    def test_remove_shrinks_list(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        buffer_list.insert(-1, _buffer(Gst, b"bc"))
        buffer_list.remove(0, 1)
        assert buffer_list.length() == 1
        assert buffer_list.get(0).extract_dup(0, 2) == b"bc"

    def test_copy_preserves_length(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        copied = buffer_list.copy()
        assert copied is not buffer_list
        assert copied.length() == 1
        assert copied.get(0).extract_dup(0, 1) == b"a"

    def test_make_writable_returns_buffer_list(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        writable = buffer_list.make_writable()
        assert isinstance(writable, Gst.BufferList)
        assert writable.length() == 1

    def test_copy_result_not_writable(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        copied = buffer_list.copy()
        assert copied.is_writable() is False

    def test_len(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        buffer_list.insert(-1, _buffer(Gst, b"bc"))
        assert len(buffer_list) == 2

    def test_getitem(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        buffer_list.insert(-1, _buffer(Gst, b"bc"))
        assert buffer_list[0].extract_dup(0, 1) == b"a"
        assert buffer_list[1].extract_dup(0, 2) == b"bc"

    def test_getitem_negative_index(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        buffer_list.insert(-1, _buffer(Gst, b"bc"))
        assert buffer_list[-1].extract_dup(0, 2) == b"bc"

    def test_getitem_out_of_range(self, Gst: Any) -> None:
        import pytest

        buffer_list = Gst.BufferList.new()
        with pytest.raises(IndexError):
            _ = buffer_list[0]

    def test_iter(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        buffer_list.insert(-1, _buffer(Gst, b"bc"))
        sizes = [buf.get_size() for buf in buffer_list]
        assert sizes == [1, 2]

    def test_list(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        buffer_list.insert(-1, _buffer(Gst, b"bc"))
        sizes = [buf.get_size() for buf in list(buffer_list)]
        assert sizes == [1, 2]

    def test_repr(self, Gst: Any) -> None:
        buffer_list = Gst.BufferList.new()
        buffer_list.insert(-1, _buffer(Gst, b"a"))
        assert repr(buffer_list) == "<Gst.BufferList len=1>"
