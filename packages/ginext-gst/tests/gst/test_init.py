# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

from ginext import Gst


class TestInit:
    def test_init_already_initialized(self) -> None:
        Gst.init(None)
        assert Gst.is_initialized()

    def test_init_check(self) -> None:
        result = Gst.init_check(None)
        assert result[0]

    def test_init_python_when_initialized(self) -> None:
        Gst.init_python()

    def test_version_string(self) -> None:
        version = Gst.version_string()
        assert version.startswith("GStreamer")
