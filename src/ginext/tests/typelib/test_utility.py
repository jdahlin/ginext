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

"""Port of goi/tests/test_utility.py."""

from __future__ import annotations

import pytest

from ginext.namespace import Namespace
from ginext.tests.gi_test_utils import load_test_namespace


@pytest.fixture(scope="module")
def utility() -> Namespace:
    return load_test_namespace("Utility")


def test_enum_type_exists(utility: Namespace) -> None:
    assert hasattr(utility, "EnumType")


def test_enum_type_a(utility: Namespace) -> None:
    assert utility.EnumType.A == 0


def test_enum_type_b(utility: Namespace) -> None:
    assert utility.EnumType.B == 1


def test_enum_type_c(utility: Namespace) -> None:
    assert utility.EnumType.C == 2


def test_flag_type_exists(utility: Namespace) -> None:
    assert hasattr(utility, "FlagType")


def test_flag_type_a(utility: Namespace) -> None:
    assert utility.FlagType.A == 1


def test_flag_type_b(utility: Namespace) -> None:
    assert utility.FlagType.B == 2


def test_flag_type_c(utility: Namespace) -> None:
    assert utility.FlagType.C == 4


def test_object_instantiable(utility: Namespace) -> None:
    assert utility.Object() is not None


def test_struct_instantiable(utility: Namespace) -> None:
    assert utility.Struct() is not None


def test_buffer_instantiable(utility: Namespace) -> None:
    assert utility.Buffer() is not None


def test_byte_instantiable(utility: Namespace) -> None:
    assert utility.Byte() is not None


def test_tagged_value_instantiable(utility: Namespace) -> None:
    assert utility.TaggedValue() is not None


def test_union_instantiable(utility: Namespace) -> None:
    assert utility.Union() is not None


def test_dir_foreach(utility: Namespace) -> None:
    utility.dir_foreach("/tmp", lambda path: None)
