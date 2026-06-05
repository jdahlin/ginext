# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango

from .support import make_layout


def test_layout_line_exposes_index_geometry_and_direction() -> None:
    layout = make_layout("abc def")
    line = layout.get_line_readonly(0)

    assert line is not None
    assert line.get_start_index() == 0
    assert line.get_length() >= 0
    assert line.get_resolved_direction() == Pango.Direction.LTR
    assert line.get_height() > 0
    assert isinstance(line.get_x_ranges(0, 3), list)
    assert line.x_to_index(0).index_ == 0
    assert line.index_to_x(1, False) >= 0
