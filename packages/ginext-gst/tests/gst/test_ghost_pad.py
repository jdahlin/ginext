# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestGhostPad:
    def test_create_with_target(self) -> None:
        src = Gst.ElementFactory.make("fakesrc", None)
        src_pad = src.get_static_pad("src")
        ghost = Gst.GhostPad("ghost-src", src_pad)
        assert ghost is not None
        assert ghost.get_property("direction") == Gst.PadDirection.SRC

    def test_create_with_direction(self) -> None:
        ghost = Gst.GhostPad("ghost", direction=Gst.PadDirection.SINK)
        assert ghost is not None
        assert ghost.get_property("direction") == Gst.PadDirection.SINK

    def test_create_no_args(self) -> None:
        with pytest.raises(TypeError):
            Gst.GhostPad("ghost")
