# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext.namespace import Namespace


class TestValueList:
    def test_create_empty(self, Gst: Namespace) -> None:
        vl = Gst.ValueList()
        assert len(vl) == 0

    def test_create_with_list(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([1, 2, 3])
        assert len(vl) == 3

    def test_str(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([1, 2, 3])
        assert str(vl) == "{1,2,3}"

    def test_repr(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([1])
        assert repr(vl) == "<Gst.ValueList {1}>"

    def test_iter(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([4, 5, 6])
        assert list(vl) == [4, 5, 6]

    def test_non_iterable_raises(self, Gst: Namespace) -> None:
        with pytest.raises(TypeError):
            Gst.ValueList(1)

    def test_append(self, Gst: Namespace) -> None:
        vl = Gst.ValueList()
        vl.append(42)
        assert len(vl) == 1
        assert vl[0] == 42

    def test_prepend(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([2])
        vl.prepend(1)
        assert vl[0] == 1
        assert vl[1] == 2

    def test_getitem(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([10, 20, 30])
        assert vl[0] == 10
        assert vl[2] == 30

    def test_setitem(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([1, 2])
        vl[0] = 99
        assert vl[0] == 99

    def test_len(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([1, 2, 3])
        assert len(vl) == 3

    def test_append_value_static(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([1])
        Gst.ValueList.append_value(vl, 2)
        assert len(vl) == 2

    def test_prepend_value_static(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([2])
        Gst.ValueList.prepend_value(vl, 1)
        assert vl[0] == 1

    def test_get_size_static(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([1, 2])
        assert Gst.ValueList.get_size(vl) == 2

    def test_list(self, Gst: Namespace) -> None:
        vl = Gst.ValueList([1, 2, 3])
        assert list(vl) == [1, 2, 3]
