# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext.namespace import Namespace


class TestCaps:
    def test_new_empty(self, Gst: Namespace) -> None:
        caps = Gst.Caps()
        assert caps is not None
        assert caps.is_empty()

    def test_new_from_string(self, Gst: Namespace) -> None:
        caps = Gst.Caps("video/x-raw")
        assert not caps.is_empty()

    def test_new_from_caps(self, Gst: Namespace) -> None:
        caps1 = Gst.Caps("video/x-raw")
        caps2 = Gst.Caps(caps1)
        assert caps2 is not None
        assert not caps2.is_empty()
        assert caps1 is not caps2

    def test_new_from_structure(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("audio/x-raw")
        caps = Gst.Caps(s)
        assert caps.get_size() == 1

    def test_new_from_list(self, Gst: Namespace) -> None:
        s1 = Gst.Structure.new_empty("video/x-raw")
        s2 = Gst.Structure.new_empty("audio/x-raw")
        caps = Gst.Caps([s1, s2])
        assert caps.get_size() == 2

    def test_new_from_tuple(self, Gst: Namespace) -> None:
        s1 = Gst.Structure.new_empty("video/x-raw")
        s2 = Gst.Structure.new_empty("audio/x-raw")
        caps = Gst.Caps((s1, s2))
        assert caps.get_size() == 2

    def test_new_invalid_type(self, Gst: Namespace) -> None:
        with pytest.raises(TypeError):
            Gst.Caps(42)

    def test_str(self, Gst: Namespace) -> None:
        caps = Gst.Caps.new_empty()
        assert str(caps) == "EMPTY"

    def test_getitem(self, Gst: Namespace) -> None:
        caps = Gst.Caps("video/x-raw; audio/x-raw")
        s = caps[0]
        assert s.get_name() == "video/x-raw"

    def test_getitem_out_of_range(self, Gst: Namespace) -> None:
        caps = Gst.Caps.new_empty()
        with pytest.raises(IndexError):
            _ = caps[0]

    def test_iter(self, Gst: Namespace) -> None:
        caps = Gst.Caps("video/x-raw; audio/x-raw")
        structs = list(caps)
        assert len(structs) == 2

    def test_len(self, Gst: Namespace) -> None:
        caps = Gst.Caps("video/x-raw; audio/x-raw")
        assert len(caps) == 2

    def test_repr(self, Gst: Namespace) -> None:
        caps = Gst.Caps("video/x-raw")
        assert repr(caps) == "<Gst.Caps video/x-raw>"
