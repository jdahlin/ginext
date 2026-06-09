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

"""GObject GType surface.

ginext models a GType as a *class* in a metaclass hierarchy (``_GTypeMeta``),
not as an instantiable wrapper object: the base is ``ginext.gobject.GType`` and
each concrete GType is a subclass carrying a ``gimeta`` with the integer GType.
``compat_gtype_from_raw(gtype, name)`` builds (or returns the cached) subclass
for a raw GType, and ``GObject.type_from_name`` resolves a name to its integer
GType (0 when unknown). GType is internal — it is reachable via
``ginext.gobject`` but not exposed at the top level of ``ginext`` nor as
``GObject.Type``.
"""

from __future__ import annotations

from typing import Any

import pytest

from ginext.gobject.gtype import GType, compat_gtype_from_raw

# G_TYPE_OBJECT is a well-known fundamental: 80 (GLib reserves the low
# fundamental type ids).
G_TYPE_OBJECT = 80


@pytest.fixture
def GObject() -> Any:
    from ginext import private

    private.require_namespace("GObject", "2.0")
    from ginext import GObject

    return GObject


def _gtype(GObject: Any, name: str) -> Any:
    """Resolve a GType *name* to its ginext GType subclass."""
    return compat_gtype_from_raw(GObject.type_from_name(name), name)


def test_gtype_base_is_a_class() -> None:
    assert isinstance(GType, type)
    assert GType.__name__ == "GType"


def test_gtype_from_raw_int(GObject: Any) -> None:
    gt = compat_gtype_from_raw(G_TYPE_OBJECT, "GObject")
    assert int(gt) == G_TYPE_OBJECT
    assert gt.name == "GObject"
    assert int(gt) == GObject.type_from_name("GObject")


def test_gtype_invalid_is_zero() -> None:
    gt = compat_gtype_from_raw(0, "")
    assert int(gt) == 0
    assert gt.name == ""


def test_gtype_equality_and_hash() -> None:
    a = compat_gtype_from_raw(G_TYPE_OBJECT, "GObject")
    b = compat_gtype_from_raw(G_TYPE_OBJECT, "GObject")
    c = compat_gtype_from_raw(0, "")
    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert a == G_TYPE_OBJECT
    assert {a, b, c} == {a, c}


def test_gtype_from_name_roundtrip(GObject: Any) -> None:
    gt = _gtype(GObject, "GObject")
    assert gt.name == "GObject"
    assert int(gt) != 0


def test_type_pyobject_is_synthesized(GObject: Any) -> None:
    value = GObject.type_from_name("PyObject")
    assert value != 0


def test_gtype_from_name_unknown_returns_zero(GObject: Any) -> None:
    assert GObject.type_from_name("ThisTypeDoesNotExist1234") == 0


def test_gtype_is_a(GObject: Any) -> None:
    # GBinding is a registered GObject subclass.
    gobj = _gtype(GObject, "GObject")
    binding = _gtype(GObject, "GBinding")
    assert binding.is_a(gobj) is True
    assert gobj.is_a(binding) is False


def test_gtype_children_includes_subtypes(GObject: Any) -> None:
    gobj = _gtype(GObject, "GObject")
    binding = _gtype(GObject, "GBinding")
    assert binding in gobj.children


def test_gtype_pytype_unset_returns_none(GObject: Any) -> None:
    # GBoxed is a fundamental with no Python wrapper registered against it.
    gt = _gtype(GObject, "GBoxed")
    assert gt.pytype is None


def test_gtype_pytype_resolves_registered_class(GObject: Any) -> None:
    # The bare GObject GType maps back to the GObject.Object wrapper class.
    # pytype prefers the pygobject-compat wrapper when PYGOBJECT_COMPAT is on,
    # so pin the feature off (another test can leave it cached-on) to assert
    # native resolution deterministically.
    from ginext import features

    was = features.is_enabled(features.PYGOBJECT_COMPAT)
    features.set_enabled(features.PYGOBJECT_COMPAT, False)
    try:
        assert _gtype(GObject, "GObject").pytype is GObject.Object
    finally:
        features.set_enabled(features.PYGOBJECT_COMPAT, was)


def test_gtype_repr_uses_name(GObject: Any) -> None:
    gt = _gtype(GObject, "GObject")
    assert "GObject" in repr(gt)


def test_gtype_not_exposed_at_top_level() -> None:
    import ginext
    from ginext import private

    # GType is internal: reachable via ginext.gobject, but not surfaced on the
    # top-level ginext package, the private module, or the GObject namespace.
    assert "GType" not in vars(ginext)
    assert "Type" not in vars(ginext)
    assert "Type" not in vars(private)

    from ginext import GObject

    assert getattr(GObject, "Type", None) is None
