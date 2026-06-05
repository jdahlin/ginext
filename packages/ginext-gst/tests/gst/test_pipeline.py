# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

from ginext import Gst


class TestPipeline:
    def test_pipeline_create(self) -> None:
        pipe = Gst.Pipeline()
        assert pipe is not None
        assert isinstance(pipe, Gst.Pipeline)

    def test_pipeline_create_named(self) -> None:
        pipe = Gst.Pipeline("mypipe")
        assert pipe.get_name() == "mypipe"

    def test_pipeline_state_change(self) -> None:
        pipe = Gst.parse_launch("fakesrc num-buffers=3 ! fakesink")
        assert pipe.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
        pipe.set_state(Gst.State.NULL)
