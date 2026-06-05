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

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(scope="module")
def GLib() -> Any:
    from ginext import GLib

    return GLib


def test_find_program_in_path(GLib: Any) -> None:
    # Pick a program that is guaranteed to be on PATH for the platform.
    # On Windows find_program_in_path appends ".exe", so match the stem.
    program = "cmd" if sys.platform == "win32" else "bash"

    found = GLib.find_program_in_path(program)

    assert found is not None
    assert Path(found).stem.lower() == program
    assert Path(found).exists()
    assert GLib.find_program_in_path("non existing") is None


@pytest.mark.parametrize(
    ("text", "length", "expected"),
    [
        pytest.param("a&bä", -1, "a&amp;bä", id="str"),
        pytest.param(b"a&b\x05", -1, "a&amp;b&#x5;", id="bytes"),
        pytest.param(b"a\x05\x01\x02", 2, "a&#x5;", id="explicit-length"),
    ],
)
def test_markup_escape_text(
    GLib: Any, text: str | bytes, length: int, expected: str
) -> None:
    assert GLib.markup_escape_text(text, length) == expected


@pytest.mark.parametrize(
    ("setter", "getter"),
    [
        pytest.param("set_prgname", "get_prgname", id="program-name"),
        pytest.param(
            "set_application_name", "get_application_name", id="application-name"
        ),
    ],
)
def test_process_names_round_trip(GLib: Any, setter: str, getter: str) -> None:
    getattr(GLib, setter)("moo")

    assert getattr(GLib, getter)() == "moo"


def test_xdg_dirs(GLib: Any) -> None:
    assert os.path.sep in GLib.get_user_data_dir()
    assert os.path.sep in GLib.get_user_special_dir(
        GLib.UserDirectory.DIRECTORY_DESKTOP
    )
    assert all(os.path.sep in path for path in GLib.get_system_config_dirs())
    assert all(isinstance(path, str) for path in GLib.get_system_data_dirs())


def test_main_depth(GLib: Any) -> None:
    assert GLib.main_depth() == 0


def test_filenames(GLib: Any) -> None:
    assert GLib.filename_display_name("foo") == "foo"
    assert GLib.filename_display_basename("bar/foo") == "foo"

    filename, bytes_read, bytes_written = GLib.filename_from_utf8("aäb", -1)
    assert isinstance(filename, str)
    assert bytes_read >= 3
    assert bytes_written >= 3

    filename, bytes_read, bytes_written = GLib.filename_from_utf8("aäb", 1)
    assert filename == "a"
    assert bytes_read == 1
    assert bytes_written == 1


def test_uri_extract(GLib: Any) -> None:
    uris = GLib.uri_list_extract_uris("""# some comment
http://example.com
https://my.org/q?x=1&y=2
            http://gnome.org/new""")

    assert uris == [
        "http://example.com",
        "https://my.org/q?x=1&y=2",
        "http://gnome.org/new",
    ]


def test_main_context(GLib: Any) -> None:
    context = GLib.MainContext()

    assert context.is_owner() in {True, False}
    assert context.pending() is False
    assert context.iteration(False) is False
    assert GLib.MainContext.default() == GLib.main_context_default()


@pytest.mark.parametrize(
    ("name", "value", "expected"),
    [
        pytest.param("unichar_isprint", "a", True, id="isprint-str-true"),
        pytest.param("unichar_isprint", "\x01", False, id="isprint-str-false"),
        pytest.param("unichar_isalpha", "z", True, id="isalpha-str-true"),
        pytest.param("unichar_isalpha", "5", False, id="isalpha-str-false"),
        pytest.param("unichar_isdigit", "5", True, id="isdigit-str-true"),
        pytest.param("unichar_isdigit", "a", False, id="isdigit-str-false"),
        pytest.param("unichar_isspace", "\n", True, id="isspace-str-true"),
        pytest.param("unichar_isspace", "a", False, id="isspace-str-false"),
        pytest.param("unichar_isprint", ord("a"), True, id="isprint-int-true"),
        pytest.param("unichar_isalpha", ord("z"), True, id="isalpha-int-true"),
        pytest.param("unichar_isdigit", ord("5"), True, id="isdigit-int-true"),
    ],
)
def test_unichar_accepts_str_and_int_codepoint(
    GLib: Any, name: str, value: str | int, expected: bool
) -> None:
    assert getattr(GLib, name)(value) is expected


def test_unichar_rejects_multi_char_str(GLib: Any) -> None:
    with pytest.raises((ValueError, TypeError)):
        GLib.unichar_isprint("ab")
