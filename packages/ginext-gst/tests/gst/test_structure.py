# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext.namespace import Namespace


class TestStructure:
    def test_new_from_string(self, Gst: Namespace) -> None:
        s = Gst.Structure("video/x-raw")
        assert s.get_name() == "video/x-raw"

    def test_new_from_string_with_fields(self, Gst: Namespace) -> None:
        s = Gst.Structure("video/x-raw", width=1920, height=1080)
        assert s.get_name() == "video/x-raw"
        assert s["width"] == 1920
        assert s["height"] == 1080

    def test_new_from_structure(self, Gst: Namespace) -> None:
        s1 = Gst.Structure("test")
        s2 = Gst.Structure(s1)
        assert s2.get_name() == "test"
        assert s1 is not s2

    def test_new_invalid(self, Gst: Namespace) -> None:
        with pytest.raises(TypeError):
            Gst.Structure(42)

    def test_getitem(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("test")
        s.set_value("x", 42)
        assert s["x"] == 42

    def test_getitem_missing(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("test")
        with pytest.raises(KeyError):
            _ = s["missing"]

    def test_setitem(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("test")
        s["foo"] = "bar"
        assert s["foo"] == "bar"

    def test_len(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("test")
        assert len(s) == 0
        s.set_value("a", 1)
        assert len(s) == 1
        s.set_value("b", 2)
        assert len(s) == 2

    def test_iter_keys(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("test")
        s.set_value("a", 1)
        s.set_value("b", 2)
        keys = list(s)
        assert set(keys) == {"a", "b"}

    def test_items(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("test")
        s.set_value("x", 10)
        s.set_value("y", 20)
        items = dict(s.items())
        assert items == {"x": 10, "y": 20}

    def test_keys(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("test")
        s.set_value("m", 1)
        s.set_value("n", 2)
        keys = list(s.keys())
        assert set(keys) == {"m", "n"}

    def test_str(self, Gst: Namespace) -> None:
        s = Gst.Structure.new_empty("test")
        assert str(s) == "test;"

    def test_repr(self, Gst: Namespace) -> None:
        s = Gst.Structure("video/x-raw", width=1920)
        assert repr(s) == "<Gst.Structure video/x-raw, width=(int)1920;>"

    def test_dict(self, Gst: Namespace) -> None:
        s = Gst.Structure("video/x-raw", width=1920, height=1080)
        assert dict(s) == {"width": 1920, "height": 1080}
