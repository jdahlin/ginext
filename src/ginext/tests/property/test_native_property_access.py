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

"""Plain-attribute access to *any* GObject property.

Declared ``Property()`` fields, introspected properties, and properties
inherited from a native base class are all reachable as ``obj.name`` — a
descriptor is synthesized from the pspec on first access (see
``ginext.gobject.properties._PspecProperty``) and cached on the class. This is
what lets ``selected.playlist.title`` chain without ``get_property`` or
``.props``.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def Gio() -> Any:
    from ginext import private

    private.require_namespace("Gio", "2.0")
    from ginext import Gio

    return Gio


def test_introspected_property_reads_as_attribute(Gio: Any) -> None:
    action = Gio.SimpleAction.new("act", None)
    # "enabled" is an introspected GObject property, not a declared field.
    assert action.enabled is True
    assert action.name == "act"


def test_introspected_property_writes_as_attribute(Gio: Any) -> None:
    action = Gio.SimpleAction.new("act", None)
    action.enabled = False
    assert action.enabled is False
    assert action.get_property_by_name("enabled") is False


def test_internal_gobject_typelib_methods_stay_hidden(Gio: Any) -> None:
    from ginext import GObject as GObjectNamespace

    hidden = ("set_property", "get_property", "ref", "unref")
    missing = object()
    cached = {
        name: GObjectNamespace.Object.__dict__.get(name, missing) for name in hidden
    }
    for name, value in cached.items():
        if value is not missing:
            delattr(GObjectNamespace.Object, name)
    try:
        for name in hidden:
            assert name not in dir(GObjectNamespace.Object)

        action = Gio.SimpleAction.new("act", None)
        for name in hidden:
            assert not hasattr(action, name)
    finally:
        for name, value in cached.items():
            if value is not missing:
                setattr(GObjectNamespace.Object, name, value)


def test_dashed_property_name_uses_underscore_attribute(Gio: Any) -> None:
    action = Gio.SimpleAction.new("act", None)
    # The GObject property is "parameter-type"; the attribute is underscored.
    assert action.parameter_type is None


def test_synthesized_property_surfaces_in_annotations(Gio: Any) -> None:
    action = Gio.SimpleAction.new("act", None)
    _ = action.enabled
    assert "enabled" in type(action).__annotations__


def test_unknown_attribute_still_raises(Gio: Any) -> None:
    action = Gio.SimpleAction.new("act", None)
    with pytest.raises(AttributeError):
        _ = action.definitely_not_a_property


def test_subclass_of_native_mixes_declared_and_inherited(
    Gio: Any, Property: Any
) -> None:
    """Subclass a native class, add a declared Property, and fetch both the new
    field and the inherited introspected properties consistently — all as plain
    attributes."""

    class MyAction(Gio.SimpleAction):  # type: ignore[misc]
        label: str = Property(default="untitled")

    action = MyAction(name="open", enabled=True)

    # Declared field on the subclass.
    assert action.label == "untitled"
    action.label = "Open File"
    assert action.label == "Open File"

    # Properties inherited from the native Gio.SimpleAction base.
    assert action.name == "open"
    assert action.enabled is True
    action.enabled = False
    assert action.enabled is False


def test_subclass_advertises_inherited_properties_without_access(
    Gio: Any, Property: Any
) -> None:
    """A Python subclass lists its declared field *and* every inherited GObject
    property in __annotations__ / dir() up front — no prior attribute access
    needed (dataclass-subclass style)."""

    base_annotations_before = dict(vars(Gio.SimpleAction).get("__annotations__", {}))

    class TaggedAction(Gio.SimpleAction):  # type: ignore[misc]
        label: str = Property(default="x")

    annotations = TaggedAction.__annotations__
    assert "label" in annotations  # declared field
    assert "enabled" in annotations  # inherited, never accessed
    assert "name" in annotations
    assert "enabled" in dir(TaggedAction)

    # Subclass setup must not mutate the imported base class.
    base_annotations = vars(Gio.SimpleAction).get("__annotations__", {})
    assert base_annotations == base_annotations_before


def test_object_valued_property_chains(GObject: Any, Property: Any) -> None:
    """`a.b.c` works when b is an object-valued property holding another
    GObject that itself exposes c as a property."""

    class Inner(GObject):  # type: ignore[misc]
        title: str = Property(default="")

    class Outer(GObject):  # type: ignore[misc]
        inner: "Inner | None" = Property(default=None)

    leaf = Inner()
    leaf.title = "MostPlayed"
    root = Outer()
    root.inner = leaf

    assert root.inner.title == "MostPlayed"
