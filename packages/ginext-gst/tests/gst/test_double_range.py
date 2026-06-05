# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestDoubleRange:
    def test_create(self) -> None:
        r = Gst.DoubleRange(0.0, 1.0)
        assert str(r) == "(double)[0.0,1.0]"

    def test_str(self) -> None:
        r = Gst.DoubleRange(0.0, 1.0)
        assert str(r) == "(double)[0.0,1.0]"

    def test_repr(self) -> None:
        r = Gst.DoubleRange(0.0, 1.0)
        assert repr(r) == "<Gst.DoubleRange [0.0,1.0]>"

    def test_invalid_start_ge_stop(self) -> None:
        with pytest.raises(TypeError):
            Gst.DoubleRange(1.0, 0.0)
