# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_rectangle


def test_rectangle_contains_intersects_and_unions() -> None:
    left = make_rectangle(0, 0, 10, 10)
    right = make_rectangle(5, 5, 10, 10)

    assert repr(left) == "Gdk.Rectangle(x=0, y=0, width=10, height=10)"
    assert left.contains_point(1, 1) is True
    assert left.contains_point(20, 20) is False
    assert left.intersect(right)[0] is True

    union = left.union(right)
    assert union.x == 0
    assert union.y == 0
    assert union.width == 15
    assert union.height == 15
