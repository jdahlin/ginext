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

"""GObject.props proxy round-trips.

`obj.props` is pygobject's property-bag accessor; native ginext reads/writes
declared properties as plain attributes and introspected ones via
get_property/set_property. The proxy is installed by the compat layer
(gi._gobject_props / repository._install_gobject_props), so these tests — which
exercise the proxy itself — live in the compat suite. Relocated from the core
paramspec backlog when props moved out of native ginext.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def GIM() -> Any:
    from gi.repository import GIMarshallingTests

    return GIMarshallingTests


@pytest.fixture
def GLib() -> Any:
    from gi.repository import GLib

    return GLib


def test_props_proxy_reads_and_writes_properties(GIM: Any) -> None:
    obj = GIM.PropertiesObject()
    assert obj.props.some_int == 0

    obj.props.some_int = 7

    assert obj.props.some_int == 7
    assert obj.get_property("some-int") == 7


def _approx(want: float, rel: float = 1e-6) -> Any:
    return lambda got: got == pytest.approx(want, rel=rel)


def _eq(want: object) -> Any:
    return lambda got: got == want


def _is(want: object) -> Any:
    return lambda got: got is want


def _strv(want: list[str]) -> Any:
    return lambda got: list(got) == want


def _bytes(want: bytes) -> Any:
    return lambda got: bytes(got) == want


def _variant_int(want: int) -> Any:
    return lambda got: got is not None and got.unpack() == want


# (prop_name, value_factory(GIM, GLib), check(got))
#
# `value_factory` is a callable so namespace fixtures resolve lazily —
# parametrize values evaluate at collection time and the fixtures
# aren't bound yet then.
_PROP_CASES = [
    ("some_boolean", lambda G, L: True, _is(True)),
    ("some_char", lambda G, L: -5, _eq(-5)),
    ("some_uchar", lambda G, L: 250, _eq(250)),
    ("some_int", lambda G, L: 12345, _eq(12345)),
    ("some_uint", lambda G, L: 12345, _eq(12345)),
    ("some_long", lambda G, L: 12345, _eq(12345)),
    ("some_ulong", lambda G, L: 12345, _eq(12345)),
    ("some_int64", lambda G, L: 12345678901, _eq(12345678901)),
    ("some_uint64", lambda G, L: 12345678901, _eq(12345678901)),
    ("some_float", lambda G, L: 1.5, _approx(1.5)),
    ("some_double", lambda G, L: 3.14159, _eq(3.14159)),
    ("some_string", lambda G, L: "hello goi", _eq("hello goi")),
    ("some_enum", lambda G, L: int(G.GEnum.VALUE2), lambda v: int(v) == 1),
    ("some_flags", lambda G, L: int(G.Flags.VALUE2), lambda v: int(v) == 2),
    ("some_strv", lambda G, L: ["alice", "bob"], _strv(["alice", "bob"])),
    ("some_variant", lambda G, L: L.Variant("i", 42), _variant_int(42)),
    ("some_byte_array", lambda G, L: b"raw bytes", _bytes(b"raw bytes")),
]


def _case_id(case: Any) -> Any:
    # pytest.param wraps each marked case; reach into .values for its
    # tuple, otherwise it's already a tuple.
    values = case.values if hasattr(case, "values") else case
    return values[0]


@pytest.mark.parametrize(
    ("prop_name", "value_factory", "check"),
    _PROP_CASES,
    ids=[_case_id(case) for case in _PROP_CASES],
)
def test_props_proxy_writes_every_relevant_property(
    GIM: Any, GLib: Any, prop_name: str, value_factory: Any, check: Any
) -> None:
    """Round-trip a value through every property type the target-typed
    marshaller is expected to handle. C dispatch is in
    src/marshal/gvalue.c::goi_py_to_gvalue_targeted — a switch keyed
    on G_TYPE_FUNDAMENTAL(target) plus runtime checks for boxed
    subtypes (G_TYPE_STRV, G_TYPE_VARIANT, G_TYPE_BYTE_ARRAY, ...)."""
    obj = GIM.PropertiesObject()
    value = value_factory(GIM, GLib)
    setattr(obj.props, prop_name, value)
    got = getattr(obj.props, prop_name)
    assert check(got), f"round-trip mismatch for {prop_name}: got {got!r}"


def test_props_proxy_writes_object_property_identity(GIM: Any) -> None:
    """Object identity has to round-trip too; broken out from the
    table-driven test because the comparator needs a closure over the
    just-constructed `value` to assert `got is value` (object
    properties keep the wrapper, not just an equal copy)."""
    obj = GIM.PropertiesObject()
    other = GIM.Object()
    obj.props.some_object = other
    assert obj.props.some_object is other


def test_props_proxy_round_trips_object_properties(GIM: Any) -> None:
    obj = GIM.PropertiesObject()
    other = GIM.Object()

    obj.set_property("some-object", other)
    got = obj.props.some_object

    assert got is not None
    assert got is other or repr(got) == repr(other)
