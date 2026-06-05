# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_path


def test_path_measure_reports_length_path_and_tolerance() -> None:
    from ginext import Gsk

    path = make_path()
    measure = Gsk.PathMeasure.new(path)

    assert measure.get_length() > 0
    assert measure.get_path() is not None
    assert measure.get_tolerance() == 0.5
