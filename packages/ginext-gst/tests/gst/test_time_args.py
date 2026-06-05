# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestTIME_ARGS:
    def test_clock_time_none(self) -> None:
        assert Gst.TIME_ARGS(Gst.CLOCK_TIME_NONE) == "CLOCK_TIME_NONE"

    def test_zero(self) -> None:
        assert Gst.TIME_ARGS(0) == "0:00:00.000000000"

    def test_one_second(self) -> None:
        assert Gst.TIME_ARGS(Gst.SECOND) == "0:00:01.000000000"

    def test_one_minute(self) -> None:
        assert Gst.TIME_ARGS(60 * Gst.SECOND) == "0:01:00.000000000"

    def test_one_hour(self) -> None:
        assert Gst.TIME_ARGS(3600 * Gst.SECOND) == "1:00:00.000000000"

    def test_typeerror_none(self) -> None:
        with pytest.raises(TypeError):
            Gst.TIME_ARGS(None)

    def test_typeerror_str(self) -> None:
        with pytest.raises(TypeError):
            Gst.TIME_ARGS("string")
