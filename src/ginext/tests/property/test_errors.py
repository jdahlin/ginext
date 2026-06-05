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

import pytest
from typing import Any


def test_empty_property_name_raises(make_subclass: Any, Property: Any) -> None:
    with pytest.raises(ValueError, match="property name cannot be empty"):
        make_subclass({"": (int, Property())}, prefix="EmptyName")


def test_property_keyword_arg_misspelling_raises(Property: Any) -> None:
    with pytest.raises(TypeError):
        Property(deafult="oops")


def test_property_positional_must_be_a_type(Property: Any) -> None:
    # The single positional argument is the value type; a non-type value
    # (e.g. a default) must be passed by keyword.
    with pytest.raises(TypeError):
        Property("hello")
    assert Property(int).type is int
