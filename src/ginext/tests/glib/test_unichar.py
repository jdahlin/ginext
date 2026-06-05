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

"""Port of goi/tests/test_GLib_Unichar.py."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("fn_name", "ch", "expected"),
    [
        pytest.param("unichar_isprint", "a", True, id="isprint-str-true"),
        pytest.param("unichar_isprint", "\x01", False, id="isprint-str-false"),
        pytest.param("unichar_isalpha", "z", True, id="isalpha-str-true"),
        pytest.param("unichar_isalpha", "5", False, id="isalpha-str-false"),
        pytest.param("unichar_isdigit", "5", True, id="isdigit-str-true"),
        pytest.param("unichar_isdigit", "a", False, id="isdigit-str-false"),
        pytest.param("unichar_isspace", "\n", True, id="isspace-str-true"),
        pytest.param("unichar_isspace", "a", False, id="isspace-str-false"),
    ],
)
def test_unichar_accepts_str(fn_name: str, ch: str, expected: bool) -> None:
    from ginext import GLib

    assert getattr(GLib, fn_name)(ch) is expected


@pytest.mark.parametrize(
    ("fn_name", "codepoint", "expected"),
    [
        pytest.param("unichar_isprint", ord("a"), True, id="isprint-int"),
        pytest.param("unichar_isalpha", ord("z"), True, id="isalpha-int"),
        pytest.param("unichar_isdigit", ord("5"), True, id="isdigit-int"),
    ],
)
def test_unichar_accepts_int_codepoint(
    fn_name: str, codepoint: int, expected: bool
) -> None:
    from ginext import GLib

    assert getattr(GLib, fn_name)(codepoint) is expected


def test_unichar_rejects_multi_char_str() -> None:
    from ginext import GLib

    with pytest.raises((TypeError, ValueError)):
        GLib.unichar_isprint("ab")
