# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestFractionRange:
    def test_create(self) -> None:
        r = Gst.FractionRange(Gst.Fraction(1, 4), Gst.Fraction(3, 4))
        assert str(r) == "(fraction)[1/4,3/4]"

    def test_str(self) -> None:
        r = Gst.FractionRange(Gst.Fraction(1, 4), Gst.Fraction(3, 4))
        assert str(r) == "(fraction)[1/4,3/4]"

    def test_repr(self) -> None:
        r = Gst.FractionRange(Gst.Fraction(1, 4), Gst.Fraction(3, 4))
        assert repr(r) == "<Gst.FractionRange [1/4,3/4]>"

    def test_invalid_not_fraction(self) -> None:
        pytest.raises(TypeError, Gst.FractionRange, 0.25, Gst.Fraction(3, 4))

    def test_invalid_start_ge_stop(self) -> None:
        with pytest.raises(TypeError):
            Gst.FractionRange(Gst.Fraction(3, 4), Gst.Fraction(1, 4))
