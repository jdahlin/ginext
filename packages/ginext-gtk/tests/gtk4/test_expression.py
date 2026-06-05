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

import itertools
import os
from typing import Any

import pytest


import ginext


_type_seq = itertools.count()


@pytest.fixture(autouse=True)
def _setup() -> None:
    for ns, ver in (("Gtk", "4.0"), ("GObject", "2.0"), ("Gio", "2.0")):
        ginext.private.require_namespace(ns, ver)


@pytest.fixture
def Gtk(_setup: None) -> Any:
    from ginext import Gtk

    return Gtk


@pytest.fixture
def GObjectRepo(_setup: None) -> Any:
    from ginext import GObject

    return GObject


@pytest.fixture
def expression_types(_setup: None) -> tuple[Any, Any]:
    from ginext import GObject

    suffix = f"{os.getpid()}_{next(_type_seq)}"

    class File(GObject.Object, type_name=f"GoiExpressionFile{suffix}"):
        display_name = GObject.Property(str, default="")

    class Row(GObject.Object, type_name=f"GoiExpressionRow{suffix}"):
        name = GObject.Property(str, default="")
        file = GObject.Property(File)

    return File, Row


def test_expression_property_constructor_supports_param_specs(
    Gtk: Any,
    GObjectRepo: Any,
    expression_types: tuple[Any, Any],
) -> None:
    File, Row = expression_types

    expression = Gtk.PropertyExpression(Row.file, File.display_name)

    assert isinstance(expression, Gtk.PropertyExpression)
    assert GObjectRepo.type_name(expression.get_value_type()) == "gchararray"
    assert "file" in Row.gimeta.pspecs
    assert "display_name" in File.gimeta.pspecs


def test_expression_classes_use_fundamental_base(Gtk: Any, GObjectRepo: Any) -> None:
    from ginext.fundamental import Fundamental

    assert issubclass(Gtk.Expression, Fundamental)
    assert not issubclass(Gtk.Expression, GObjectRepo.Object)


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        pytest.param(("name",), "gchararray", id="single-descriptor"),
        pytest.param(("file", "display_name"), "gchararray", id="chained-descriptors"),
    ],
)
def test_expression_property_constructor_accepts_property_descriptors(
    Gtk: Any,
    GObjectRepo: Any,
    expression_types: tuple[Any, Any],
    parts: tuple[str, ...],
    expected: str,
) -> None:
    File, Row = expression_types
    owner = {"name": Row, "file": Row, "display_name": File}
    args = tuple(getattr(owner[name], name) for name in parts)

    expression = Gtk.PropertyExpression(*args)

    assert isinstance(expression, Gtk.PropertyExpression)
    assert GObjectRepo.type_name(expression.get_value_type()) == expected


def test_expression_property_constructor_accepts_string_path(
    Gtk: Any,
    GObjectRepo: Any,
    expression_types: tuple[Any, Any],
) -> None:
    _File, Row = expression_types

    expression = Gtk.PropertyExpression("name", this_type=Row)
    assert isinstance(expression, Gtk.PropertyExpression)
    assert GObjectRepo.type_name(expression.get_value_type()) == "gchararray"


def test_expression_property_constructor_accepts_dotted_string_path(
    Gtk: Any,
    GObjectRepo: Any,
    expression_types: tuple[Any, Any],
) -> None:
    _File, Row = expression_types

    expression = Gtk.PropertyExpression("file.display_name", this_type=Row)
    assert isinstance(expression, Gtk.PropertyExpression)
    assert GObjectRepo.type_name(expression.get_value_type()) == "gchararray"


def test_expression_property_constructor_accepts_explicit_type_and_property_name(
    Gtk: Any,
    GObjectRepo: Any,
    expression_types: tuple[Any, Any],
) -> None:
    _File, Row = expression_types

    expression = Gtk.PropertyExpression(Row, property_name="name")
    assert isinstance(expression, Gtk.PropertyExpression)
    assert GObjectRepo.type_name(expression.get_value_type()) == "gchararray"


def test_expression_property_constructor_accepts_explicit_parent_expression(
    Gtk: Any,
    GObjectRepo: Any,
    expression_types: tuple[Any, Any],
) -> None:
    File, Row = expression_types

    parent = Gtk.PropertyExpression(Row, property_name="file")
    expression = Gtk.PropertyExpression(File, parent, property_name="display_name")
    assert isinstance(expression, Gtk.PropertyExpression)
    assert GObjectRepo.type_name(expression.get_value_type()) == "gchararray"


def test_expression_property_constructor_rejects_property_without_context(
    Gtk: Any,
) -> None:
    with pytest.raises(TypeError, match="requires this_type"):
        Gtk.PropertyExpression("name")


def test_expression_constant_and_try_constructors(
    Gtk: Any, GObjectRepo: Any, expression_types: tuple[Any, Any]
) -> None:
    _File, Row = expression_types

    constant = Gtk.ConstantExpression("Untitled")
    fallback = Gtk.TryExpression(
        Gtk.PropertyExpression(Row, property_name="name"), constant
    )

    assert isinstance(constant, Gtk.ConstantExpression)
    assert isinstance(fallback, Gtk.TryExpression)
    assert GObjectRepo.type_name(fallback.get_value_type()) == "gchararray"


def test_try_expression_requires_explicit_expressions(
    Gtk: Any,
    expression_types: tuple[Any, Any],
) -> None:
    _File, Row = expression_types

    with pytest.raises(TypeError, match="requires Gtk.Expression values"):
        Gtk.TryExpression("name", Gtk.ConstantExpression("Untitled"), this_type=Row)


pytestmark = [pytest.mark.xdist_group("gtk")]
