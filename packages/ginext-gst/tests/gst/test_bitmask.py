# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestBitmask:
    def test_create(self) -> None:
        b = Gst.Bitmask(0xFF)
        assert b == 0xFF

    def test_str(self) -> None:
        b = Gst.Bitmask(0xFF)
        assert str(b) == "0xff"

    def test_eq(self) -> None:
        b = Gst.Bitmask(0xFF)
        assert b == 0xFF

    def test_invalid_not_int(self) -> None:
        pytest.raises(TypeError, Gst.Bitmask, 3.14)

    def test_get_value_from_structure(self) -> None:
        s, _ = Gst.Structure.from_string("test,field=(bitmask)0xf0f0")
        val = s["field"]
        assert val == 0xF0F0

    def test_set_value_into_structure(self) -> None:
        # Python -> GValue (the from_py converter).
        s, _ = Gst.Structure.from_string("test,x=(int)1")
        s.set_value("field", Gst.Bitmask(0xF0F0))
        assert s["field"] == 0xF0F0
