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

from ..conftest import read_numeric_pspec


def test_subclass_property_override_replaces_default_bounds_and_docs(
    GObject: Any, Property: Any, pspec_default: Any, pspec_info: Any
) -> None:
    class Base(GObject):  # type: ignore[misc]
        value: int = Property(
            default=1,
            minimum=0,
            maximum=10,
            nick="base value",
            blurb="base blurb",
        )

    class Child(Base):
        value: int = Property(
            default=2,
            minimum=1,
            maximum=20,
            nick="child value",
            blurb="child blurb",
        )

    base_pspec = Base.gimeta.pspecs["value"]
    child_pspec = Child.gimeta.pspecs["value"]

    assert base_pspec != child_pspec

    base_info = pspec_info(base_pspec)
    child_info = pspec_info(child_pspec)
    assert base_info.value_type_name == "gint64"
    assert child_info.value_type_name == "gint64"
    assert base_info.nick == "base value"
    assert child_info.nick == "child value"
    assert base_info.blurb == "base blurb"
    assert child_info.blurb == "child blurb"
    assert base_info.owner_type != child_info.owner_type

    base_numeric = read_numeric_pspec(base_pspec)
    child_numeric = read_numeric_pspec(child_pspec)
    assert (base_numeric.minimum, base_numeric.maximum, base_numeric.default_value) == (
        0,
        10,
        1,
    )
    assert (
        child_numeric.minimum,
        child_numeric.maximum,
        child_numeric.default_value,
    ) == (1, 20, 2)
    assert pspec_default(base_pspec) == 1
    assert pspec_default(child_pspec) == 2

    base = Base()
    child = Child()
    assert base.value == 1
    assert child.value == 2
    child.value = 7
    assert child.value == 7
    assert base.value == 1


def test_subclass_property_override_can_change_python_base_type(
    GObject: Any, Property: Any, pspec_info: Any
) -> None:
    class Base(GObject):  # type: ignore[misc]
        value: int = Property(default=1)

    class Child(Base):
        value: str = Property(  # type: ignore[assignment]
            default="hello", nick="child string", blurb="string"
        )

    base = Base()
    child = Child()

    assert pspec_info(Base.gimeta.pspecs["value"]).value_type_name == "gint64"
    child_info = pspec_info(Child.gimeta.pspecs["value"])
    assert child_info.value_type_name == "gchararray"
    assert child_info.nick == "child string"
    assert child_info.blurb == "string"

    assert base.value == 1
    assert child.value == "hello"
    child.value = "updated"
    assert child.value == "updated"
    assert child.get_property_by_name("value") == "updated"
    assert base.value == 1


def test_subclass_property_override_can_replace_inherited_native_property(
    Gio: Any, Property: Any, pspec_info: Any
) -> None:
    class TaggedAction(Gio.SimpleAction):  # type: ignore[misc]
        enabled: str = Property(default="yes", nick="Enabled text", blurb="override")

    base = Gio.SimpleAction.new("act", None)
    child = TaggedAction(name="act")

    child_info = pspec_info(TaggedAction.gimeta.pspecs["enabled"])
    assert child_info.value_type_name == "gchararray"
    assert child_info.nick == "Enabled text"
    assert child_info.blurb == "override"

    assert base.enabled is True
    assert child.enabled == "yes"
    child.enabled = "no"
    assert child.enabled == "no"
    assert child.get_property_by_name("enabled") == "no"
