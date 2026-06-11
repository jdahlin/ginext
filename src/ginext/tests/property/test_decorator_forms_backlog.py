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

"""Backlog for richer ginext ``Property`` declaration forms.

The active property suite covers the native storage path:

    class Item(GObject):
        title: str = Property(default="")

This file keeps the next layer of API expectations in ginext terms rather than
as a copied PyGObject/goi compatibility suite: class mutation interactions and
object-valued property round-trips. The native ``Property`` is value-backed
only; the getter/setter decorator forms are a PyGObject compatibility feature
covered by the gi-compat property suite.
"""

import itertools
from typing import Any, cast

import pytest


_subclass_seq = itertools.count()


def _unique_name(prefix: str) -> str:
    return f"{prefix}{next(_subclass_seq):04d}"


# --- Native storage descriptor surface -----------------------------------


def test_property_class_attr_returns_descriptor_and_pspec(
    GObject: Any, Property: Any
) -> None:
    class Foo(GObject, type_name=_unique_name("PropClassAttr")):  # type: ignore[misc, call-arg]
        title: str = Property(default="default")

    assert Foo.__dict__["title"].name == "title"
    assert Foo.__dict__["title"] is Foo.title
    assert Foo.gimeta.pspecs["title"] != 0
    assert isinstance(Foo.__dict__["title"], Property)


def test_property_assignment_form_default(GObject: Any, Property: Any) -> None:
    class Foo(GObject, type_name=_unique_name("PropAssignDefault")):  # type: ignore[misc, call-arg]
        title: str = Property(default="hello")

    assert Foo().title == "hello"


def test_property_assignment_form_round_trip(GObject: Any, Property: Any) -> None:
    class Foo(GObject, type_name=_unique_name("PropAssignRoundTrip")):  # type: ignore[misc, call-arg]
        title: str = Property(default="")

    f = Foo()
    f.title = "world"
    assert f.title == "world"
    assert f.get_property_by_name("title") == "world"


def test_plain_property_uses_native_storage_not_instance_dict(
    GObject: Any, Property: Any
) -> None:
    class Foo(GObject, type_name=_unique_name("PropNativeStorage")):  # type: ignore[misc, call-arg]
        title: str = Property(default="")
        count: int = Property(default=0)

    f = Foo()
    f.title = "world"
    f.count = 7

    assert f.title == "world"
    assert f.get_property_by_name("title") == "world"
    assert f.count == 7
    assert f.get_property_by_name("count") == 7
    assert "title" not in f.__dict__
    assert "count" not in f.__dict__


# --- Class mutation / descriptor precedence -------------------------------


def test_native_property_cache_ignores_replaced_class_attribute(
    GObject: Any, Property: Any
) -> None:
    class Foo(GObject, type_name=_unique_name("PropCacheReplaceClassAttr")):  # type: ignore[misc, call-arg]
        value: int = Property(default=1)

    f = Foo()
    assert f.value == 1

    cast("Any", Foo).value = "class-value"

    assert f.value == "class-value"  # type: ignore[comparison-overlap]
    assert f.get_property_by_name("value") == 1

    f.set_property_by_name("value", 2)
    assert f.get_property_by_name("value") == 2
    assert f.value == "class-value"  # type: ignore[comparison-overlap]

    f.value = 7
    assert f.value == 7
    assert f.__dict__["value"] == 7
    assert f.get_property_by_name("value") == 2


@pytest.mark.xfail(reason="Property class-attribute cache form pending", strict=False)
def test_native_property_cache_ignores_deleted_class_attribute(
    GObject: Any, Property: Any
) -> None:
    class Foo(GObject, type_name=_unique_name("PropCacheDeleteClassAttr")):  # type: ignore[misc, call-arg]
        value: int = Property(default=1)

    f = Foo()
    f.value = 5
    assert f.value == 5

    del Foo.value

    with pytest.raises(AttributeError):
        _ = f.value
    assert f.get_property_by_name("value") == 5


def test_native_property_cache_uses_replacement_data_descriptor(
    GObject: Any, Property: Any
) -> None:
    class Foo(GObject, type_name=_unique_name("PropCacheReplaceDescriptor")):  # type: ignore[misc, call-arg]
        value: int = Property(default=1)

    f = Foo()
    assert f.value == 1

    seen = []

    def get_value(self: Any) -> str:
        return "descriptor-value"

    def set_value(self: Any, value: Any) -> None:
        seen.append(value)

    cast("Any", Foo).value = property(get_value, set_value)

    assert f.value == "descriptor-value"  # type: ignore[comparison-overlap]
    f.value = 9
    assert seen == [9]
    assert f.get_property_by_name("value") == 1

    f.set_property_by_name("value", 4)
    assert f.value == "descriptor-value"  # type: ignore[comparison-overlap]
    assert f.get_property_by_name("value") == 4


def test_native_property_cache_respects_subclass_plain_override(
    GObject: Any, Property: Any
) -> None:
    class Base(GObject, type_name=_unique_name("PropCacheBaseOverride")):  # type: ignore[misc, call-arg]
        value: int = Property(default=1)

    class Child(Base, type_name=_unique_name("PropCacheChildOverride")):  # type: ignore[call-arg]
        value = "child-value"  # type: ignore[assignment]

    base = Base()
    assert base.value == 1

    child = Child()
    assert child.value == "child-value"
    assert child.get_property_by_name("value") == 1

    cast("Any", child).value = 12
    assert child.value == 12  # type: ignore[comparison-overlap]
    assert child.__dict__["value"] == 12
    assert child.get_property_by_name("value") == 1
    assert base.value == 1


def test_native_property_cache_respects_parent_descriptor_replacement(
    GObject: Any, Property: Any
) -> None:
    class Base(GObject, type_name=_unique_name("PropCacheParentReplace")):  # type: ignore[misc, call-arg]
        value: int = Property(default=1)

    class Child(Base, type_name=_unique_name("PropCacheParentReplaceChild")):  # type: ignore[call-arg]
        pass

    base = Base()
    child = Child()
    assert base.value == 1
    assert child.value == 1

    cast("Any", Base).value = "parent-class-value"

    assert base.value == "parent-class-value"  # type: ignore[comparison-overlap]
    assert child.value == "parent-class-value"  # type: ignore[comparison-overlap]
    assert base.get_property_by_name("value") == 1
    assert child.get_property_by_name("value") == 1


def test_native_property_cache_keeps_unrelated_class_mutation_fast_path_valid(
    GObject: Any, Property: Any
) -> None:
    class Foo(GObject, type_name=_unique_name("PropCacheUnrelatedMutation")):  # type: ignore[misc, call-arg]
        value: int = Property(default=1)

    f = Foo()
    assert f.value == 1

    Foo.unrelated = "new class attr"

    f.value = 8
    assert f.value == 8
    assert f.get_property_by_name("value") == 8
    assert Foo.unrelated == "new class attr"


# --- Decorator surface ----------------------------------------------------


@pytest.mark.parametrize(
    ("annotation", "default", "new"),
    [
        pytest.param(str, "", "hello", id="str"),
        pytest.param(int, 0, 42, id="int"),
        pytest.param(bool, False, True, id="bool"),
        pytest.param(float, 0.0, 3.14, id="float"),
    ],
)
def test_property_typed_round_trip(
    GObject: Any, Property: Any, annotation: Any, default: Any, new: Any
) -> None:
    class Foo(GObject, type_name=_unique_name(f"PropTyped{annotation.__name__}")):  # type: ignore[misc, call-arg]
        v: annotation = Property(default=default)

    f = Foo()
    assert f.v == default
    f.v = new
    assert f.v == new


# --- Object-valued property round trips ----------------------------------


@pytest.mark.xfail(
    reason="flaky under xdist (process-global boxed/gtype state); passes serially",
    strict=False,
)
def test_property_boxed_type_round_trip(GObject: Any, Property: Any) -> None:
    from ginext import GLib

    class Song(GObject, type_name=_unique_name("PropBoxedSong")):  # type: ignore[misc, call-arg]
        last_played: Any = Property(default=None)

    s = Song()
    assert s.last_played is None

    dt = GLib.DateTime.new_now_local()
    s.last_played = dt
    read_back = s.last_played
    assert read_back is not None
    assert read_back.format_iso8601() == dt.format_iso8601()

    s.last_played = None
    assert s.last_played is None

    notifies = []
    s.connect("notify::last-played", lambda obj, pspec: notifies.append("fired"))
    s.last_played = GLib.DateTime.new_now_local()
    assert notifies == ["fired"]


def test_property_survives_liststore_round_trip(GObject: Any, Property: Any) -> None:
    from ginext import Gio

    class Inner(GObject, type_name=_unique_name("RoundTripInner")):  # type: ignore[misc, call-arg]
        pass

    class Outer(GObject, type_name=_unique_name("RoundTripOuter")):  # type: ignore[misc, call-arg]
        payload: Inner = Property(default=None)

        def __init__(self, payload: Any) -> None:
            super().__init__()
            self.payload = payload

    inner = Inner()
    outer = Outer(inner)
    assert outer.payload is inner

    store = Gio.ListStore(item_type=Outer.gimeta.gtype)
    store.append(outer)
    del outer
    back = store[0]

    # back is freshly wrapped from the store, so read through the property
    # system (get_property_by_name) which falls back to the C accessor — the
    # plain _Property descriptor's fast path isn't populated on a bare re-wrap.
    assert back.get_property_by_name("payload") is not None, (
        "wrapper round-trip lost the Property value"
    )
    assert isinstance(back.get_property_by_name("payload"), Inner)


def test_quoted_optional_object_property_annotation(
    GObject: Any, Property: Any
) -> None:
    class Inner(GObject, type_name=_unique_name("QuotedOptionalInner")):  # type: ignore[misc, call-arg]
        pass

    class Outer(GObject, type_name=_unique_name("QuotedOptionalOuter")):  # type: ignore[misc, call-arg]
        payload: "Inner | None" = Property(default=None)

    outer = Outer()
    assert outer.payload is None
    inner = Inner()
    outer.payload = inner
    assert outer.payload is inner
