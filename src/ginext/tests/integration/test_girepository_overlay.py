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

from typing import Any

import pytest


def _require_typed_info(info: Any) -> None:
    if not hasattr(info, "arg_names"):
        pytest.skip("GIRepository-3.0 typelib unavailable")


def test_callable_arg_names_handles_bool_out_indices() -> None:
    from ginext import private

    kind, info = private.namespace_find("GLib", "2.0", "timeout_add")

    assert kind == "function"
    _require_typed_info(info)
    assert info.has_user_data_slot is True
    assert info.arg_names == ["priority", "interval", "function"]


def test_callable_arg_names_hides_out_args() -> None:
    from ginext import private

    kind, info = private.namespace_find(
        "GIMarshallingTests", "1.0", "array_fixed_out_struct"
    )

    assert kind == "function"
    _require_typed_info(info)
    assert info.arg_names == []


# --- __match_args__ for structural pattern matching ------------------------


def test_info_match_args_set_on_tiers() -> None:
    """Each tier of the GIBaseInfo hierarchy exposes its salient attributes
    (name first) as __match_args__."""
    from ginext.GIRepository import (
        BaseInfo,
        CallableInfo,
        ConstantInfo,
        EnumInfo,
        RegisteredTypeInfo,
    )

    assert BaseInfo.__match_args__ == ("name", "namespace")
    assert CallableInfo.__match_args__ == ("name", "arg_names")
    assert RegisteredTypeInfo.__match_args__ == ("name", "gtype")
    assert EnumInfo.__match_args__ == ("name", "members")
    assert ConstantInfo.__match_args__ == ("name", "value")


def test_info_match_args_inherited_by_leaves() -> None:
    """Leaf types inherit their tier's __match_args__ by ordinary lookup."""
    from ginext.GIRepository import (
        CallableInfo,
        EnumInfo,
        FlagsInfo,
        FunctionInfo,
        ObjectInfo,
        RegisteredTypeInfo,
        StructInfo,
    )

    assert FunctionInfo.__match_args__ == CallableInfo.__match_args__
    assert FlagsInfo.__match_args__ == EnumInfo.__match_args__
    assert ObjectInfo.__match_args__ == RegisteredTypeInfo.__match_args__
    assert StructInfo.__match_args__ == RegisteredTypeInfo.__match_args__


def test_constant_info_positional_match() -> None:
    from ginext import private
    from ginext.GIRepository import ConstantInfo

    _kind, info = private.namespace_find("GLib", "2.0", "MAXINT32")

    match info:
        case ConstantInfo(name, value):
            assert name == "MAXINT32"
            assert value == 2147483647
        case _:  # pragma: no cover - guards against a regression in matching
            raise AssertionError("ConstantInfo did not match positionally")


def test_flags_info_matches_before_enum_via_subclass() -> None:
    """FlagsInfo is a subclass of EnumInfo, so an EnumInfo arm would also catch
    it; matching FlagsInfo first (and binding its inherited args) must work."""
    from ginext import private
    from ginext.GIRepository import EnumInfo, FlagsInfo

    _kind, info = private.namespace_find("GLib", "2.0", "IOFlags")

    match info:
        case FlagsInfo(name, members):
            assert name == "IOFlags"
            assert len(members) > 0
        case EnumInfo():  # pragma: no cover
            raise AssertionError("flags matched the EnumInfo arm")
        case _:  # pragma: no cover
            raise AssertionError("IOFlags did not match FlagsInfo")
