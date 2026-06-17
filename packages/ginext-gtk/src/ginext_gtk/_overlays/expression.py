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

"""Pythonic constructors for Gtk.Expression types.

GTK-4 only: Expression, PropertyExpression, ConstantExpression,
ObjectExpression, TryExpression.
"""

from __future__ import annotations

import dis
import operator as _operator
from typing import TYPE_CHECKING, Any, cast

import ginext
from ginext.gobject import gobjectclass as _gobject_root
from ginext.gobject.gtype import compat_gtype_from_raw
from ginext import GObject, Gtk

if TYPE_CHECKING:
    pass

overlay = Gtk.overlay

_ATTRGETTER_TYPE = type(_operator.attrgetter("x"))

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _property_lookup_variants(name: str) -> tuple[str, ...]:
    variants = [name]
    dashed = name.replace("_", "-")
    underscored = name.replace("-", "_")
    if dashed not in variants:
        variants.append(dashed)
    if underscored not in variants:
        variants.append(underscored)
    return tuple(variants)


def _is_param_spec_like(value: object) -> bool:
    return hasattr(value, "value_type") and hasattr(value, "name")


_PropertyCls: Any = _gobject_root.Property
_ParamSpec: Any = GObject.ParamSpec


def _is_property_descriptor(value: object) -> bool:
    if isinstance(value, _PropertyCls):
        return True
    pspec = getattr(value, "pspec", None)
    return hasattr(value, "name") and _is_param_spec_like(pspec)


def _pspec_for_value(value: Any) -> Any:
    if _is_property_descriptor(value):
        return value.pspec
    if isinstance(value, _ParamSpec):
        return value
    if _is_param_spec_like(value):
        return value
    pspec = getattr(value, "pspec", None)
    if pspec is not None and _is_param_spec_like(pspec):
        return pspec
    raise TypeError(f"expected a property or ParamSpec, got {type(value).__name__}")


def _pspec_for_name(this_type: type, name: str) -> Any:
    for key in _property_lookup_variants(name):
        for base in this_type.__mro__:
            descriptor = vars(base).get(key)
            if _is_property_descriptor(descriptor):
                return cast("Any", descriptor).pspec
        gimeta = getattr(this_type, "gimeta", None)
        pspecs = getattr(gimeta, "pspecs", None)
        if isinstance(pspecs, dict):
            pspec = pspecs.get(key)
            if pspec is not None:
                return pspec
    raise TypeError(f"{this_type.__name__} has no property {name!r}")


def _gtk_peer_class(context: object, name: str) -> Any:
    return ginext._class_from_namespace_profile(context, "Gtk", name)


def _pytype_for_value_type(value_type: Any) -> type | None:
    if value_type is None:
        return None
    pytype = getattr(value_type, "pytype", None)
    if isinstance(pytype, type):
        return pytype
    if isinstance(value_type, int):
        type_name = GObject.type_name(value_type)
        if type_name is None:
            return None
        pytype = compat_gtype_from_raw(value_type, type_name).pytype
        if isinstance(pytype, type):
            return pytype
    return None


def _property_expression_for_path(
    path: str,
    *,
    this_type: type | None,
    property_expression_cls: Any = None,
) -> Any:
    if this_type is None:
        raise TypeError("property path coercion requires this_type")
    if property_expression_cls is None:
        property_expression_cls = _gtk_peer_class(this_type, "PropertyExpression")
    names = path.split(".")
    expression = None
    current_type: type | None = this_type
    for name in names:
        assert current_type is not None
        pspec = _pspec_for_name(current_type, name)
        if expression is None:
            expression = property_expression_cls(pspec)
        else:
            expression = type(expression).new_for_pspec(expression, pspec)
        current_type = _pytype_for_value_type(pspec.value_type)
        if current_type is None:
            break
    return expression


def _attrgetter_path(value: Any) -> str | None:
    if not isinstance(value, _ATTRGETTER_TYPE):
        return None
    reduced = value.__reduce__()
    if not isinstance(reduced, tuple) or len(reduced) != 2:
        return None
    ctor, args = reduced
    if (
        ctor is not _operator.attrgetter
        or len(args) != 1
        or not isinstance(args[0], str)
    ):
        return None
    return args[0]


_LAMBDA_SUPPORTED_HINT = (
    " — supported forms: 'lambda row: row.name' or 'lambda row: row.file.display_name'"
)


def _simple_lambda_path(value: Any) -> str | None:
    if not callable(value):
        return None
    try:
        instructions = list(dis.get_instructions(value))
    except TypeError:
        return None
    if not instructions:
        return None
    opnames = {instr.opname for instr in instructions}
    if "CALL" in opnames or "PRECALL" in opnames or "LOAD_METHOD" in opnames:
        raise TypeError(
            "lambda coercion does not support method calls" + _LAMBDA_SUPPORTED_HINT
        )
    attrs: list[str] = []
    saw_fast = False
    for instr in instructions:
        if instr.opname == "RESUME":
            continue
        if instr.opname.startswith("LOAD_FAST"):
            saw_fast = True
            continue
        if instr.opname == "LOAD_ATTR" and saw_fast:
            if not isinstance(instr.argval, str):
                raise TypeError(
                    "lambda coercion found unsupported attribute operand"
                    + _LAMBDA_SUPPORTED_HINT
                )
            attrs.append(instr.argval)
            continue
        if instr.opname == "RETURN_VALUE":
            if not attrs:
                raise TypeError(
                    "lambda coercion requires at least one attribute access"
                    + _LAMBDA_SUPPORTED_HINT
                )
            return ".".join(attrs)
        raise TypeError(
            f"lambda coercion found unsupported bytecode {instr.opname!r}"
            + _LAMBDA_SUPPORTED_HINT
        )
    return None


def _coerce_expression(
    value: Any,
    *,
    this_type: type | None = None,
    expression_cls: Any = None,
) -> Any:
    if expression_cls is not None:
        expression_base_cls = _gtk_peer_class(expression_cls, "Expression")
        if isinstance(value, expression_base_cls):
            return value
    property_expression_cls = (
        _gtk_peer_class(expression_cls, "PropertyExpression")
        if expression_cls is not None
        else None
    )
    if (
        _is_property_descriptor(value)
        or isinstance(value, _ParamSpec)
        or _is_param_spec_like(value)
    ):
        if property_expression_cls is None:
            property_expression_cls = _gtk_peer_class(this_type, "PropertyExpression")
        return property_expression_cls(value)
    if isinstance(value, str):
        return _property_expression_for_path(
            value,
            this_type=this_type,
            property_expression_cls=property_expression_cls,
        )
    attr_path = _attrgetter_path(value)
    if attr_path is not None:
        return _property_expression_for_path(
            attr_path,
            this_type=this_type,
            property_expression_cls=property_expression_cls,
        )
    if callable(value):
        path = _simple_lambda_path(value)
        if path is not None:
            return _property_expression_for_path(
                path,
                this_type=this_type,
                property_expression_cls=property_expression_cls,
            )
    raise TypeError(f"Cannot convert {type(value).__name__} to Gtk.Expression")


# ---------------------------------------------------------------------------
# Pythonic mixin classes for Gtk.Expression subclasses (GTK 4 only)
# ---------------------------------------------------------------------------


class ExpressionMixin:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        return None


def _property_expression_new(
    cls: Any,
    *parts: Any,
    this_type: type | None = None,
    expression: Any = None,
    property_name: str | None = None,
) -> Any:
    if not parts:
        return super(cls, cls).__new__(cls)
    _cls: Any = cls
    if isinstance(parts[0], type):
        if len(parts) > 2:
            raise TypeError(
                "Gtk.PropertyExpression accepts at most two positional arguments "
                "before property_name"
            )
        if this_type is not None:
            raise TypeError("Gtk.PropertyExpression got multiple values for this_type")
        if property_name is None:
            raise TypeError(
                "Gtk.PropertyExpression requires property_name when the first "
                "argument is a type"
            )
        this_type = parts[0]
        if len(parts) == 2:
            if expression is not None:
                raise TypeError(
                    "Gtk.PropertyExpression got multiple values for expression"
                )
            expression = parts[1]
        pspec = _pspec_for_name(this_type, property_name)
        return _cls.new_for_pspec(expression, pspec)
    if property_name is not None or expression is not None:
        raise TypeError(
            "Gtk.PropertyExpression keyword arguments require a leading type"
        )
    if len(parts) == 1:
        part = parts[0]
        if isinstance(part, str):
            return _property_expression_for_path(
                part,
                this_type=this_type,
                property_expression_cls=cls,
            )
        return _cls.new_for_pspec(None, _pspec_for_value(part))
    expression = None
    for part in parts:
        expression = (
            cast("Any", type(expression)).new_for_pspec(
                expression,
                _pspec_for_value(part),
            )
            if expression is not None
            else _cls.new_for_pspec(None, _pspec_for_value(part))
        )
    return expression


class PropertyExpressionMixin:
    def __new__(
        cls,
        *parts: Any,
        this_type: type | None = None,
        expression: Any = None,
        property_name: str | None = None,
    ) -> Any:
        return _property_expression_new(
            cls,
            *parts,
            this_type=this_type,
            expression=expression,
            property_name=property_name,
        )


@overlay.method("PropertyExpression", name="__new__", as_staticmethod=True)
def _property_expression_overlay_new(
    cls: Any,
    *parts: Any,
    this_type: type | None = None,
    expression: Any = None,
    property_name: str | None = None,
) -> Any:
    return _property_expression_new(
        cls,
        *parts,
        this_type=this_type,
        expression=expression,
        property_name=property_name,
    )


class ConstantExpressionMixin:
    def __new__(cls, value: Any) -> Any:
        return cast("Any", cls).new_for_value(value)


class ObjectExpressionMixin:
    def __new__(cls, obj: Any) -> Any:
        return cast("Any", cls).new(obj)


class TryExpressionMixin:
    def __new__(cls, *expressions: Any, this_type: type | None = None) -> Any:
        if len(expressions) == 1 and isinstance(expressions[0], (list, tuple)):
            expressions = tuple(expressions[0])
        if not expressions:
            raise TypeError("Gtk.TryExpression requires at least one expression")
        del this_type
        expression_base_cls = _gtk_peer_class(cls, "Expression")
        normalized = []
        for expression in expressions:
            if not isinstance(expression, expression_base_cls):
                raise TypeError("Gtk.TryExpression requires Gtk.Expression values")
            normalized.append(expression)
        return cast("Any", cls).new(normalized)


# ---------------------------------------------------------------------------
# Attach mixins (GTK 4 only)
# ---------------------------------------------------------------------------

if Gtk.__version__[0] == 4:
    overlay.bases("Expression", (ExpressionMixin,))
    overlay.bases("PropertyExpression", (PropertyExpressionMixin,))
    overlay.bases("ConstantExpression", (ConstantExpressionMixin,))
    overlay.bases("ObjectExpression", (ObjectExpressionMixin,))
    overlay.bases("TryExpression", (TryExpressionMixin,))
