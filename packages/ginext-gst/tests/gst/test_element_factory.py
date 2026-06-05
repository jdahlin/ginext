# Ported from gst-python testsuite
# https://gitlab.freedesktop.org/gstreamer/gstreamer/-/tree/main/subprojects/gst-python
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestElementFactory:
    def test_make(self) -> None:
        elem = Gst.ElementFactory.make("fakesrc", None)
        assert elem is not None

    def test_make_missing_plugin(self) -> None:
        with pytest.raises(Gst.MissingPluginError):
            Gst.ElementFactory.make("nonexistent_element_xyz")

    def test_get_longname(self) -> None:
        factory = Gst.ElementFactory.find("fakesrc")
        assert factory is not None
        longname = factory.get_longname()
        assert longname is not None
        assert isinstance(longname, str)

    def test_get_description(self) -> None:
        factory = Gst.ElementFactory.find("fakesrc")
        assert factory is not None
        desc = factory.get_description()
        assert desc is not None
        assert isinstance(desc, str)

    def test_get_klass(self) -> None:
        factory = Gst.ElementFactory.find("fakesrc")
        assert factory is not None
        klass = factory.get_klass()
        assert klass is not None
        assert isinstance(klass, str)
