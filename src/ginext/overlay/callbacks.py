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

import builtins
import sys
from functools import wraps
from typing import Any, ParamSpec, TYPE_CHECKING, TypeVar, cast

from ..gobject.gobjectclass import GObject

if TYPE_CHECKING:
    from collections.abc import Callable

    from .types import CallbackArgType, CallbackArgTypes

_ATTR = "ginext_callback_arg_types"
_BOUND_ATTR = "ginext_bound_callback_gtypes"
P = ParamSpec("P")
R = TypeVar("R")


def callback_types(
    parameter_name: str, *arg_types: CallbackArgType
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        target = getattr(fn, "__func__", fn)
        mapping = dict(callback_arg_types_for(target))
        if parameter_name in mapping:
            raise ValueError(
                f"callback arg types already set for parameter {parameter_name!r}"
            )
        mapping[parameter_name] = tuple(arg_types)
        setattr(target, _ATTR, mapping)
        return fn

    return decorator


def callback_arg_types_for(obj: object) -> CallbackArgTypes:
    func = getattr(obj, "__func__", obj)
    mapping = getattr(func, _ATTR, None)
    if mapping is None:
        return {}
    return dict(mapping)


def callback_arg_types_for_body(body: Callable[..., Any]) -> CallbackArgTypes:
    return callback_arg_types_for(body)


def adapt_callback(
    owner: object,
    parameter_name: str,
    callback: Callable[P, R] | None,
) -> Callable[P, R] | None:
    if callback is None:
        return None
    arg_types = callback_arg_types_for(owner).get(parameter_name)
    if not arg_types:
        return callback

    @wraps(callback)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        converted = list(args)
        for index, expected in enumerate(arg_types):
            if index >= len(converted):
                break
            converted[index] = _convert_callback_arg(converted[index], expected)
        return cast("R", cast("Any", callback)(*converted, **kwargs))

    return wrapped


def bind_callback_types(
    owner: object,
    parameter_name: str,
    callback: Callable[P, R] | None,
) -> Callable[P, R] | None:
    if callback is None:
        return None
    arg_types = callback_arg_types_for(owner).get(parameter_name)
    if not arg_types:
        return callback
    target = getattr(callback, "__func__", callback)
    resolved = tuple(_resolve_callback_arg_gtype(arg_type) for arg_type in arg_types)
    try:
        setattr(target, _BOUND_ATTR, resolved)
    except (AttributeError, TypeError):
        pass
    return callback


def _convert_callback_arg(value: object, expected: CallbackArgType) -> object:
    if value is None or not isinstance(value, int):
        return value
    expected_type = _resolve_callback_arg_type(expected)
    if expected_type is None:
        return value
    if not issubclass(expected_type, GObject):
        return value
    return sys.modules["ginext"].private.GObject.from_c(value)


def _resolve_callback_arg_type(expected: CallbackArgType) -> type | None:
    if isinstance(expected, type):
        return expected
    head, dot, tail = expected.partition(".")
    if not dot:
        return getattr(builtins, expected, None)
    if head == "builtins":
        obj = builtins
    else:
        try:
            obj = getattr(sys.modules["ginext"], head)
        except AttributeError:
            return None
    for part in tail.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            return None
    return obj if isinstance(obj, type) else None


def _resolve_callback_arg_gtype(expected: CallbackArgType) -> int:
    resolved = _resolve_callback_arg_type(expected)
    gimeta = getattr(resolved, "gimeta", None)
    gtype = getattr(gimeta, "gtype", 0)
    return int(gtype) if isinstance(gtype, int) else 0
