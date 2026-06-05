# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gdk, Gsk


def test_shadow_exposes_offsets_radius_and_color() -> None:
    shadow = Gsk.Shadow()
    color = Gdk.RGBA()
    color.parse("#336699cc")

    shadow.dx = 1.0
    shadow.dy = 2.0
    shadow.radius = 3.0

    assert shadow.dx == 1.0
    assert shadow.dy == 2.0
    assert shadow.radius == 3.0
    assert shadow.color is not None
