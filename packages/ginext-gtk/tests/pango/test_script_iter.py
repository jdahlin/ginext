# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_script_iter_reports_range_and_script() -> None:
    iterator = Pango.ScriptIter.new("abc", -1)
    range_ = iterator.get_range()

    assert range_.start == "abc"
    assert range_.end == ""
    assert range_.script == Pango.Script.LATIN
    assert iterator.next() is False
