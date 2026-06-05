# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestTagList:
    def test_create(self) -> None:
        tl = Gst.TagList()
        assert len(tl) == 0

    def test_setitem_getitem(self) -> None:
        tl = Gst.TagList()
        tl[Gst.TAG_TITLE] = "Test"
        assert tl[0] == "Test"
        assert tl[Gst.TAG_TITLE] == "Test"

    def test_len(self) -> None:
        tl = Gst.TagList()
        tl[Gst.TAG_TITLE] = "Test"
        tl[Gst.TAG_ARTIST] = "Artist"
        assert len(tl) == 2

    def test_keys(self) -> None:
        tl = Gst.TagList()
        tl[Gst.TAG_TITLE] = "Test"
        keys = tl.keys()
        assert Gst.TAG_TITLE in keys

    def test_iter(self) -> None:
        tl = Gst.TagList()
        tl[Gst.TAG_TITLE] = "Test"
        assert list(tl) == [Gst.TAG_TITLE]

    def test_items(self) -> None:
        tl = Gst.TagList()
        tl[Gst.TAG_TITLE] = "Test"
        assert list(tl.items()) == [(Gst.TAG_TITLE, "Test")]

    def test_dict(self) -> None:
        tl = Gst.TagList()
        tl[Gst.TAG_TITLE] = "Test"
        assert dict(tl) == {Gst.TAG_TITLE: "Test"}

    def test_getitem_out_of_range(self) -> None:
        tl = Gst.TagList()
        with pytest.raises(IndexError):
            _ = tl[0]

    def test_str(self) -> None:
        tl = Gst.TagList()
        assert isinstance(str(tl), str)

    def test_repr(self) -> None:
        tl = Gst.TagList()
        r = repr(tl)
        assert r.startswith("<Gst.TagList")
