# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestIntRange:
    def test_create(self) -> None:
        r = Gst.IntRange(range(0, 10, 2))
        assert r == range(0, 10, 2)

    def test_str_no_step(self) -> None:
        r = Gst.IntRange(range(0, 10))
        assert str(r) == "[0,10]"

    def test_str_with_step(self) -> None:
        r = Gst.IntRange(range(0, 10, 2))
        assert str(r) == "[0,10,2]"

    def test_repr(self) -> None:
        r = Gst.IntRange(range(0, 10, 2))
        assert repr(r) == "<Gst.IntRange [0,10,2]>"

    def test_eq_range(self) -> None:
        r = Gst.IntRange(range(0, 10, 2))
        assert r == range(0, 10, 2)

    def test_eq_intrange(self) -> None:
        r1 = Gst.IntRange(range(0, 10, 2))
        r2 = Gst.IntRange(range(0, 10, 2))
        assert r1 == r2

    def test_invalid_not_range(self) -> None:
        pytest.raises(TypeError, Gst.IntRange, 42)

    def test_invalid_start_ge_stop(self) -> None:
        with pytest.raises(TypeError):
            Gst.IntRange(range(10, 0))

    def test_invalid_start_not_multiple(self) -> None:
        with pytest.raises(TypeError):
            Gst.IntRange(range(1, 10, 2))

    def test_invalid_stop_not_multiple(self) -> None:
        with pytest.raises(TypeError):
            Gst.IntRange(range(0, 9, 2))
