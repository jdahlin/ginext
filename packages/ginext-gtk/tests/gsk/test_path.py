# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_path


def test_path_reports_string_fill_and_bounds() -> None:
    from ginext import Gsk

    path = make_path()
    parsed = Gsk.Path.parse(path.to_string())

    assert path.to_string() == "M 0 0 L 10 0 L 10 10 Z"
    assert path.is_empty() is False
    assert path.is_closed() is True
    assert path.in_fill(1, 1) is True
    assert parsed is not None
    assert path.equal(parsed) is True
    assert path.get_bounds()[0] is True
    assert path.get_tight_bounds()[0] is True
    assert path.get_stroke_bounds(__import__("ginext").Gsk.Stroke.new(1.0))[0] is True
    assert str(path) == "M 0 0 L 10 0 L 10 10 Z"
    assert repr(path) == "Gsk.Path('M 0 0 L 10 0 L 10 10 Z')"


def test_path_get_closest_point_reports_point_on_path() -> None:
    path = make_path()
    result = path.get_closest_point(5, 2)

    assert result[0] is True
