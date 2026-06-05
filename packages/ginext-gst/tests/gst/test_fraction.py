# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext.namespace import Namespace


class TestFraction:
    def test_create(self, Gst: Namespace) -> None:
        f = Gst.Fraction(1, 2)
        assert f.num == 1
        assert f.denom == 2

    def test_simplify(self, Gst: Namespace) -> None:
        f = Gst.Fraction(4, 8)
        assert f.num == 1
        assert f.denom == 2

    def test_str(self, Gst: Namespace) -> None:
        f = Gst.Fraction(1, 2)
        assert str(f) == "1/2"

    def test_repr(self, Gst: Namespace) -> None:
        f = Gst.Fraction(1, 2)
        assert repr(f) == "<Gst.Fraction 1/2>"

    def test_float(self, Gst: Namespace) -> None:
        f = Gst.Fraction(1, 4)
        assert float(f) == 0.25

    def test_eq(self, Gst: Namespace) -> None:
        assert Gst.Fraction(1, 2) == Gst.Fraction(1, 2)
        assert Gst.Fraction(1, 2) == Gst.Fraction(2, 4)

    def test_ne(self, Gst: Namespace) -> None:
        assert Gst.Fraction(1, 2) != Gst.Fraction(1, 3)

    def test_mul_fraction(self, Gst: Namespace) -> None:
        result = Gst.Fraction(1, 2) * Gst.Fraction(2, 3)
        assert result == Gst.Fraction(1, 3)

    def test_mul_int(self, Gst: Namespace) -> None:
        result = Gst.Fraction(1, 2) * 4
        assert result == Gst.Fraction(2, 1)

    def test_rmul_int(self, Gst: Namespace) -> None:
        result = 4 * Gst.Fraction(1, 2)
        assert result == Gst.Fraction(2, 1)

    def test_truediv_fraction(self, Gst: Namespace) -> None:
        result = Gst.Fraction(1, 2) / Gst.Fraction(1, 4)
        assert result == Gst.Fraction(2, 1)

    def test_truediv_int(self, Gst: Namespace) -> None:
        result = Gst.Fraction(1, 2) / 2
        assert result == Gst.Fraction(1, 4)

    def test_rtruediv_int(self, Gst: Namespace) -> None:
        result = 1 / Gst.Fraction(1, 2)
        assert result == Gst.Fraction(2, 1)

    def test_default_denom(self, Gst: Namespace) -> None:
        f = Gst.Fraction(3)
        assert f.num == 3
        assert f.denom == 1

    def test_no_args_raises(self, Gst: Namespace) -> None:
        with pytest.raises(TypeError):
            Gst.Fraction()

    def test_get_value_from_structure(self, Gst: Namespace) -> None:
        s, _ = Gst.Structure.from_string("test,field=(fraction)1/2")
        val = s["field"]
        assert val == Gst.Fraction(1, 2)

    def test_set_value_into_structure(self, Gst: Namespace) -> None:
        # Python -> GValue (the from_py converter): set a fraction from Python
        # and read it back.
        s, _ = Gst.Structure.from_string("test,x=(int)1")
        s.set_value("field", Gst.Fraction(3, 4))
        assert s["field"] == Gst.Fraction(3, 4)
