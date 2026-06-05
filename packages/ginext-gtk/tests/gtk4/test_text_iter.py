# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations


def test_forward_find_char_is_exposed() -> None:
    from ginext import Gtk

    assert callable(Gtk.TextIter.forward_find_char)


def test_forward_find_char_hides_user_data() -> None:
    from ginext import Gtk

    buffer = Gtk.TextBuffer()
    buffer.set_text("abc def", -1)
    iter_ = buffer.get_start_iter()
    seen: list[str] = []

    def _pred(ch: str) -> bool:
        seen.append(ch)
        return ch == "d"

    found = iter_.forward_find_char(_pred, None)

    assert found is True
    assert seen == ["b", "c", " ", "d"]
    assert iter_.get_char() == "d"


def test_forward_find_char_accepts_explicit_user_data() -> None:
    from ginext import Gtk

    buffer = Gtk.TextBuffer()
    buffer.set_text("abc", -1)
    iter_ = buffer.get_start_iter()
    seen: list[tuple[str, str]] = []

    def _pred(ch: str, user_data: str) -> bool:
        seen.append((ch, user_data))
        return ch == "c"

    found = iter_.forward_find_char(
        _pred,
        "sentinel",
        None,
    )

    assert found is True
    assert seen == [("b", "sentinel"), ("c", "sentinel")]
    assert iter_.get_char() == "c"


def test_forward_find_char_hides_user_data_for_keyword_arguments() -> None:
    from ginext import Gtk

    buffer = Gtk.TextBuffer()
    buffer.set_text("abc", -1)
    iter_ = buffer.get_start_iter()

    assert iter_.forward_find_char(pred=lambda ch: ch == "c", limit=None) is True
    assert iter_.get_char() == "c"
