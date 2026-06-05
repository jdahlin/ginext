# Tests for Gst.Element request-pad convenience
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

import pytest
from ginext import Gst


class TestRequestPad:
    def test_request_pad_with_pad_template(self) -> None:
        tee = Gst.ElementFactory.make("tee", None)
        templ = tee.get_pad_template("src_%u")
        pad = tee.request_pad(templ)
        try:
            assert isinstance(pad, Gst.Pad)
            name = pad.get_name()
            assert name is not None
            assert name.startswith("src_")
        finally:
            tee.release_request_pad(pad)

    def test_request_pad_with_static_pad_template(self) -> None:
        tee = Gst.ElementFactory.make("tee", None)
        templ = next(
            templ
            for templ in tee.get_factory().get_static_pad_templates()
            if templ.name_template == "src_%u"
        )
        pad = tee.request_pad(templ)
        try:
            assert isinstance(pad, Gst.Pad)
            name = pad.get_name()
            assert name is not None
            assert name.startswith("src_")
        finally:
            tee.release_request_pad(pad)

    def test_request_pad_with_template_name(self) -> None:
        tee = Gst.ElementFactory.make("tee", None)
        pad = tee.request_pad("src_%u")
        try:
            assert isinstance(pad, Gst.Pad)
            name = pad.get_name()
            assert name is not None
            assert name.startswith("src_")
        finally:
            tee.release_request_pad(pad)

    def test_request_pad_with_explicit_name(self) -> None:
        tee = Gst.ElementFactory.make("tee", None)
        pad = tee.request_pad("src_%u", "src_7")
        try:
            assert pad.get_name() == "src_7"
        finally:
            if pad is not None:
                tee.release_request_pad(pad)

    def test_request_pad_missing_template_raises_key_error(self) -> None:
        tee = Gst.ElementFactory.make("tee", None)
        with pytest.raises(KeyError):
            tee.request_pad("missing")
