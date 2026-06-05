# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestBin:
    def test_bin_add_one(self) -> None:
        pipeline = Gst.Pipeline()
        src = Gst.ElementFactory.make("fakesrc", None)
        pipeline.add(src)
        assert src.get_parent() == pipeline

    def test_bin_add_multiple(self) -> None:
        pipeline = Gst.Pipeline()
        src = Gst.ElementFactory.make("fakesrc", None)
        sink = Gst.ElementFactory.make("fakesink", None)
        pipeline.add(src, sink)
        assert src.get_parent() == pipeline
        assert sink.get_parent() == pipeline

    def test_bin_add_error(self) -> None:
        pipeline = Gst.Pipeline()
        src = Gst.ElementFactory.make("fakesrc", None)
        pipeline.add(src)
        with pytest.raises(Gst.AddError):
            pipeline.add(src)

    def test_bin_make_and_add(self) -> None:
        pipeline = Gst.Pipeline()
        elem = pipeline.make_and_add("fakesrc")
        assert elem is not None
        assert elem.get_parent() == pipeline

    def test_bin_make_and_add_missing_plugin(self) -> None:
        pipeline = Gst.Pipeline()
        with pytest.raises(Gst.MissingPluginError):
            pipeline.make_and_add("nonexistent_element_xyz")

    def test_bin_iter(self) -> None:
        pipeline = Gst.Pipeline()
        src = Gst.ElementFactory.make("fakesrc", None)
        sink = Gst.ElementFactory.make("fakesink", None)
        pipeline.add(src, sink)
        elements = list(pipeline)
        assert len(elements) == 2
        names = {e.get_name() for e in elements}
        assert src.get_name() in names
        assert sink.get_name() in names
