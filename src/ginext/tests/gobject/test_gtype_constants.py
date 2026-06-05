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

from typing import Any

import pytest

from ..conftest import GTYPE_CONSTANTS


@pytest.mark.parametrize("constant, gtype_name", GTYPE_CONSTANTS)
def test_gtype_constants_are_annotation_types(
    GType: Any, constant: str, gtype_name: str
) -> None:
    annotation = getattr(GType, constant)
    assert issubclass(annotation, GType)
    assert annotation.gtype_name == gtype_name
    assert annotation.gimeta.gtype != 0


@pytest.mark.parametrize("constant, gtype_name", GTYPE_CONSTANTS)
def test_g_type_from_name_matches_gtype_constants(
    GType: Any, constant: str, gtype_name: str
) -> None:
    from ginext import GObject

    assert GObject.type_from_name(gtype_name) == getattr(GType, constant).gimeta.gtype


def test_g_type_from_name_returns_zero_for_unknown_type() -> None:
    from ginext import GObject

    assert GObject.type_from_name("GinextNoSuchType") == 0
