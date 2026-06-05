# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_layout


def test_layout_iter_exposes_basic_cursor_and_line_state() -> None:
    layout = make_layout("abc def")
    iterator = layout.get_iter()

    assert iterator.get_index() == 0
    assert iterator.get_baseline() > 0
    assert iterator.get_line() is not None
    assert iterator.get_line_readonly() is not None
    assert iterator.get_run() is not None
    assert iterator.get_run_readonly() is not None
    assert isinstance(iterator.next_char(), bool)
    assert isinstance(iterator.next_cluster(), bool)
    assert isinstance(iterator.next_run(), bool)
    assert iterator.next_line() is False
