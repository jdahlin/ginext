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

"""GLib.Regex stays a boxed GLib object, but ginext additionally accepts a
Python re.Pattern wherever a GLib.Regex is expected, compiling it on demand."""

from __future__ import annotations

import re
from typing import Any

import pytest


@pytest.fixture(scope="module")
def GLib() -> Any:
    from ginext import GLib

    return GLib


@pytest.fixture(scope="module")
def regex_property_class(GLib: Any) -> Any:
    from ginext import GObject

    class RegexHolder(GObject.Object):
        rx = GObject.Property(type=GLib.Regex)

    return RegexHolder


def test_new_returns_glib_regex(GLib: Any) -> None:
    rx = GLib.Regex.new("[a-z]+", 0, 0)

    assert isinstance(rx, GLib.Regex)
    assert rx.get_pattern() == "[a-z]+"


def test_property_accepts_re_pattern(regex_property_class: Any, GLib: Any) -> None:
    obj = regex_property_class()

    obj.rx = re.compile("[0-9]+")

    assert isinstance(obj.rx, GLib.Regex)
    assert obj.rx.get_pattern() == "[0-9]+"


def test_property_accepts_glib_regex(regex_property_class: Any, GLib: Any) -> None:
    obj = regex_property_class()

    obj.rx = GLib.Regex.new("abc", 0, 0)

    assert obj.rx.get_pattern() == "abc"


def test_input_flag_translation(regex_property_class: Any) -> None:
    obj = regex_property_class()

    obj.rx = re.compile("ABC", re.IGNORECASE)

    ok, match_info = obj.rx.match("abc", 0)
    assert ok is True
    assert match_info.matches() is True


def test_unicode_flag_accepted(regex_property_class: Any) -> None:
    # re.compile() always carries re.UNICODE; it has no GRegex equivalent and
    # must be silently dropped rather than rejected.
    obj = regex_property_class()

    obj.rx = re.compile("x")

    assert obj.rx.get_pattern() == "x"


def test_property_none(regex_property_class: Any) -> None:
    obj = regex_property_class()

    obj.rx = re.compile("x")
    obj.rx = None

    assert obj.rx is None


def test_property_rejects_non_pattern(regex_property_class: Any) -> None:
    obj = regex_property_class()

    with pytest.raises(TypeError):
        obj.rx = "foo"
    with pytest.raises(TypeError):
        obj.rx = object()


def test_match_simple_still_works(GLib: Any) -> None:
    # match_simple takes the pattern as a plain str, unaffected by the mapping.
    assert GLib.Regex.match_simple("[a-z]+", "abc", 0, 0) is True
