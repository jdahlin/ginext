# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext.namespace import Namespace


class TestValueArray:
    def test_create_empty(self, Gst: Namespace) -> None:
        va = Gst.ValueArray()
        assert len(va) == 0

    def test_create_with_list(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1, 2, 3])
        assert len(va) == 3

    def test_append(self, Gst: Namespace) -> None:
        va = Gst.ValueArray()
        va.append(1)
        assert len(va) == 1
        assert va[0] == 1

    def test_prepend(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([2])
        va.prepend(1)
        assert va[0] == 1
        assert va[1] == 2

    def test_iter(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1, 2, 3])
        assert list(va) == [1, 2, 3]

    def test_getitem(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([10, 20])
        assert va[0] == 10
        assert va[1] == 20

    def test_setitem(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1, 2])
        va[0] = 99
        assert va[0] == 99

    def test_str(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1, 2, 3])
        assert str(va) == "<1,2,3>"

    def test_repr(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1])
        assert repr(va) == "<Gst.ValueArray <1>>"

    def test_append_value_static(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1])
        Gst.ValueArray.append_value(va, 2)
        assert len(va) == 2

    def test_prepend_value_static(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([2])
        Gst.ValueArray.prepend_value(va, 1)
        assert va[0] == 1

    def test_get_size_static(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1, 2])
        assert Gst.ValueArray.get_size(va) == 2

    def test_non_iterable_raises(self, Gst: Namespace) -> None:
        with pytest.raises(TypeError):
            Gst.ValueArray(1)

    def test_get_value_static(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1, 2, 3])
        assert Gst.ValueArray.get_value(va, 1) == 2

    def test_list(self, Gst: Namespace) -> None:
        va = Gst.ValueArray([1, 2, 3])
        assert list(va) == [1, 2, 3]
