# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_rectangle


def test_rounded_rect_initializes_and_updates_geometry() -> None:
    from ginext import Gsk

    rect = make_rectangle()
    rounded = Gsk.RoundedRect()
    rounded.init_from_rect(rect, 2.0)

    assert rounded.intersects_rect(rect) is True
    assert rounded.contains_rect(rect) is False
    assert rounded.is_rectilinear() is False
    assert rounded.offset(1, 2) is rounded
    assert rounded.shrink(1, 1, 1, 1) is rounded
    assert rounded.normalize() is rounded
