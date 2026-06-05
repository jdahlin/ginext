# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

from ginext import Gst


class TestIterator:
    def test_iterator_iterate_bin(self) -> None:
        pipe = Gst.parse_launch("fakesrc ! fakesink")
        assert isinstance(pipe, Gst.Pipeline)
        elements = list(pipe)
        assert len(elements) == 2

    def test_iterator_error(self) -> None:
        pipe = Gst.parse_launch("fakesrc ! fakesink")
        it = pipe.iterate_elements()
        elements = list(it)
        assert len(elements) == 2
