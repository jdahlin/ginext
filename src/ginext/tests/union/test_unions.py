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

from typing import TYPE_CHECKING

import pytest

from ginext.namespace import Namespace
from ginext.tests.gi_test_utils import load_test_namespace


@pytest.fixture(scope="module")
def gm() -> Namespace:
    return load_test_namespace("GIMarshallingTests")


@pytest.fixture(scope="module")
def regress() -> Namespace:
    return load_test_namespace("Regress")


@pytest.fixture(scope="module")
def utility() -> Namespace:
    return load_test_namespace("Utility")


if TYPE_CHECKING:

    def _match_union_positionally(union: object, cls: object) -> int | None: ...
else:

    def _match_union_positionally(union: object, cls: object) -> int | None:
        match union:
            case cls(integer, _real):
                return integer
            case _:
                return None


def test_union_default_constructor_and_field(gm: Namespace) -> None:
    union = gm.Union()

    assert isinstance(union, gm.Union)
    union.long_ = 42
    assert union.long_ == 42


def test_union_return_function(gm: Namespace) -> None:
    union = gm.union_returnv()

    assert isinstance(union, gm.Union)
    assert union.long_ == 42


def test_union_instance_method(gm: Namespace) -> None:
    union = gm.Union()
    union.long_ = 42

    assert union.method() is None


def test_union_unbound_method_type_check(gm: Namespace) -> None:
    with pytest.raises(TypeError):
        gm.Union.method()
    with pytest.raises(TypeError):
        gm.Union.inv(None)


def test_union_type_function_return(gm: Namespace) -> None:
    union = gm.Union.returnv()

    assert isinstance(union, gm.Union)
    assert union.long_ == 42


def test_structured_union_constructor_and_method(gm: Namespace) -> None:
    union = gm.StructuredUnion.new(gm.StructuredUnionType.SIMPLE_STRUCT)

    assert isinstance(union, gm.StructuredUnion)
    assert union.type() == gm.StructuredUnionType.SIMPLE_STRUCT


def test_structured_union_private_fields_are_not_visible(gm: Namespace) -> None:
    union = gm.StructuredUnion.new(gm.StructuredUnionType.SIMPLE_STRUCT)

    with pytest.raises(AttributeError):
        _ = union.simple_struct


def test_regress_foo_bunion_constructor_and_method(regress: Namespace) -> None:
    union = regress.FooBUnion.new()

    assert isinstance(union, regress.FooBUnion)
    assert isinstance(union.get_contained_type(), int)


def test_plain_regress_foo_event_fields(regress: Namespace) -> None:
    event = regress.FooEvent()

    event.type = 1
    event.any.send_event = 7

    assert event.type == 1
    assert event.any.send_event == 7


def test_utility_union_scalar_fields(utility: Namespace) -> None:
    union = utility.Union()

    union.integer = 42
    assert union.integer == 42

    union.real = 3.5
    assert union.real == pytest.approx(3.5)


def test_union_match_args_lists_scalar_fields(utility: Namespace) -> None:
    """Unions expose their readable primitive-scalar fields as __match_args__
    too — the field order is well-defined (declaration order) even though the
    storage overlaps. The non-scalar `pointer` field is excluded."""
    assert utility.Union.__match_args__ == ("integer", "real")


def test_union_positional_pattern_match(utility: Namespace) -> None:
    union = utility.Union()
    union.integer = 42

    assert _match_union_positionally(union, utility.Union) == 42
