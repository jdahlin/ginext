# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_coverage_set_get_copy_and_max() -> None:
    coverage = Pango.Coverage.new()
    coverage.set(65, Pango.CoverageLevel.EXACT)

    assert coverage.get(65) == Pango.CoverageLevel.EXACT

    copy = coverage.copy()
    assert copy.get(65) == Pango.CoverageLevel.EXACT
