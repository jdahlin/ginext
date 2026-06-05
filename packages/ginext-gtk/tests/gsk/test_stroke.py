# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gsk


def test_stroke_reports_width_caps_join_and_dash_state() -> None:
    stroke = Gsk.Stroke.new(2.0)
    stroke.set_line_cap(Gsk.LineCap.ROUND)
    stroke.set_line_join(Gsk.LineJoin.BEVEL)
    stroke.set_dash([1.0, 2.0])
    stroke.set_dash_offset(0.5)
    stroke.set_miter_limit(3.0)

    assert stroke.get_line_width() == 2.0
    assert stroke.get_line_cap() == Gsk.LineCap.ROUND
    assert stroke.get_line_join() == Gsk.LineJoin.BEVEL
    assert stroke.get_dash() == [1.0, 2.0]
    assert stroke.get_dash_offset() == 0.5
    assert stroke.get_miter_limit() == 3.0
    assert stroke.copy().get_line_width() == 2.0
