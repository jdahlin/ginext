# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_matrix_transforms_points_and_distances() -> None:
    matrix = Pango.Matrix()
    matrix.xx = 1.0
    matrix.yy = 1.0

    assert matrix.transform_point(1.0, 2.0) == (1.0, 2.0)

    matrix.translate(2, 3)
    assert matrix.transform_point(1.0, 2.0) == (3.0, 5.0)

    matrix.scale(2, 2)
    assert matrix.transform_distance(1, 1) == (2.0, 2.0)

    copy = matrix.copy()
    assert copy is not None
    assert copy.xx == 2.0
    assert copy.yy == 2.0
    assert copy.x0 == 2.0
    assert copy.y0 == 3.0
