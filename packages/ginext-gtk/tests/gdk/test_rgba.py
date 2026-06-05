# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gdk


def test_rgba_parses_copies_and_formats() -> None:
    color = Gdk.RGBA()

    assert color.parse("#336699cc") is True
    assert color.to_string() == "rgba(51,102,153,0.8)"
    assert color.is_clear() is False
    assert color.is_opaque() is False

    copy = color.copy()
    assert color.equal(copy) is True
    assert color.hash() > 0
    assert repr(color) == "Gdk.RGBA('rgba(51,102,153,0.8)')"
