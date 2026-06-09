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

"""Build `inspect.Signature` objects for GI callables from their type info.

`inspect.signature(some_gi_function)` (and `.__signature__`) returns a real
Signature whose parameters mirror the callable's IN/INOUT arguments — typed from
the GI type tags, nullable args defaulting to None — and whose return annotation
mirrors the GI return type. The callable-descriptor wrappers attach this lazily.
"""

from __future__ import annotations

import collections.abc
import inspect
import keyword
import sys
from typing import Any, cast

# GITypeTag values (girepository 2.0, stable ABI).
_VOID = 0
_BOOLEAN = 1
_INT8 = 2
_UINT8 = 3
_INT16 = 4
_UINT16 = 5
_INT32 = 6
_UINT32 = 7
_INT64 = 8
_UINT64 = 9
_FLOAT = 10
_DOUBLE = 11
_GTYPE = 12
_UTF8 = 13
_FILENAME = 14
_ARRAY = 15
_INTERFACE = 16
_GLIST = 17
_GSLIST = 18
_GHASH = 19
_ERROR = 20
_UNICHAR = 21

# GIDirection values.
_DIR_OUT = 1
_DIR_INOUT = 2

_SCALAR: dict[int, type] = {
    _BOOLEAN: bool,
    _INT8: int,
    _UINT8: int,
    _INT16: int,
    _UINT16: int,
    _INT32: int,
    _UINT32: int,
    _INT64: int,
    _UINT64: int,
    _FLOAT: float,
    _DOUBLE: float,
    _UTF8: str,
    _FILENAME: str,
    _UNICHAR: str,
}


def _resolve_namespace(name: str, context: Any) -> Any:
    """Return the live namespace `name` in the callable's ABI profile.

    Annotations must resolve in the same profile as the callable — e.g. under
    pygobject-compat `GObject.GType`/`GObject.Value` exist only on the compat
    GObject namespace, not the native one.
    """
    if name == context.name:
        return context.load_namespace()
    from . import defaults
    from .abi import NamespaceContext

    version = defaults.resolve_version(name)
    if version is None:
        return getattr(sys.modules["ginext"], name)
    return NamespaceContext(name, version, context.profile).load_namespace()


def _safe_param_name(name: str) -> str:
    """Make a GI argument name usable as an `inspect.Parameter` name.

    GI names are valid C identifiers, but some collide with Python keywords
    (e.g. an arg literally named `in`), which `inspect.Parameter` rejects. Append
    an underscore in that case, matching PyGObject's `in` -> `in_` convention.
    """
    if keyword.iskeyword(name) or not name.isidentifier():
        return f"{name}_"
    return name


def _resolve_interface(iface_info: Any, context: Any) -> Any:
    """Resolve an INTERFACE type's referenced info to its live Python class
    (object/struct/boxed/enum/flags) in the callable's profile.

    Falls back to `Any` when the type has no name in this ABI profile (e.g.
    `GObject.Value` is absent from the native GObject namespace) so that the
    Signature stays buildable rather than the whole `__signature__` raising.
    """
    try:
        namespace = _resolve_namespace(iface_info.namespace, context)
        return getattr(namespace, iface_info.name)
    except AttributeError, ImportError:
        return Any


def _callable_annotation(callback_info: Any, context: Any) -> Any:
    """`Callable[[arg types...], return type]` for a callback interface."""
    arg_types = [
        annotation_for_type(callback_info.get_arg(i).get_type_info(), context)
        for i in range(callback_info.get_n_args())
    ]
    ret = annotation_for_type(callback_info.get_return_type(), context)
    return collections.abc.Callable[arg_types, ret]


def annotation_for_type(type_info: Any, context: Any) -> Any:
    """Map a GITypeInfo to a Python type annotation, resolving interface and
    fundamental types in `context`'s ABI profile."""
    tag = type_info.get_tag()
    scalar = _SCALAR.get(tag)
    if scalar is not None:
        return scalar
    if tag == _VOID:
        return None
    if tag == _GTYPE:
        try:
            return _resolve_namespace("GObject", context).GType
        except AttributeError, ImportError:
            return Any
    if tag in (_ARRAY, _GLIST, _GSLIST):
        # Subscripting with a runtime type object is exactly the intent here.
        return list[annotation_for_type(type_info.get_param_type(0), context)]  # type: ignore[misc]
    if tag == _GHASH:
        key = annotation_for_type(type_info.get_param_type(0), context)
        value = annotation_for_type(type_info.get_param_type(1), context)
        return dict[key, value]  # type: ignore[valid-type]
    if tag == _INTERFACE:
        iface = type_info.get_interface()
        if type(iface).__name__ == "CallbackInfo":
            return _callable_annotation(iface, context)
        return _resolve_interface(iface, context)
    if tag == _ERROR:
        try:
            return _resolve_namespace("GLib", context).Error
        except AttributeError, ImportError:
            return Any
    return Any


def _maybe_optional(annotation: Any, nullable: bool) -> tuple[Any, Any]:
    """Return (annotation, default): nullable args become `T | None = None`."""
    if not nullable:
        return annotation, inspect.Parameter.empty
    return annotation | None, None


def build_signature(
    info: Any,
    *,
    has_self: bool,
    context: Any,
    keyword_only_after: int | None = None,
) -> inspect.Signature:
    """Build the Signature for a GI callable.

    Parameters are the IN/INOUT args (in `arg_names` order, already filtered of
    array-length and closure/destroy companions), each typed from its pspec and
    defaulting to None when nullable/optional. `self` is prepended for methods.
    The return annotation mirrors the GI return type (None for void).

    When `keyword_only_after` is set, visible parameters at that index and
    beyond (not counting `self`) are emitted as KEYWORD_ONLY — set by the
    `overlay.keyword_only(...)` declaration.
    """
    parameters: list[inspect.Parameter] = []
    if has_self:
        parameters.append(
            inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)
        )

    args = [info.get_arg(i) for i in range(info.get_n_args())]
    args_by_name = {arg.name: arg for arg in args}

    # Companion args (an array's length, a callback's user_data/destroy) are
    # implicit — they appear in neither the parameters nor the return tuple.
    skip: set[int] = set()
    for arg in args:
        type_info = arg.get_type_info()
        if type_info.get_tag() == _ARRAY:
            length = type_info.get_array_length_index()
            if length >= 0:
                skip.add(length)
        for companion in (arg.get_closure_index(), arg.get_destroy_index()):
            if companion >= 0:
                skip.add(companion)

    for index, name in enumerate(info.arg_names):
        arg = args_by_name.get(name)
        param_name = _safe_param_name(name)
        kind = (
            inspect.Parameter.KEYWORD_ONLY
            if keyword_only_after is not None and index >= keyword_only_after
            else inspect.Parameter.POSITIONAL_OR_KEYWORD
        )
        if arg is None:
            parameters.append(inspect.Parameter(param_name, kind))
            continue
        annotation = annotation_for_type(arg.get_type_info(), context)
        nullable = arg.may_be_null() or arg.is_optional()
        annotation, default = _maybe_optional(annotation, nullable)
        parameters.append(
            inspect.Parameter(
                param_name,
                kind,
                annotation=annotation,
                default=default,
            )
        )

    # The return is the C return value (if any) followed by every OUT/INOUT arg
    # in argument order, collapsed to a single annotation or a tuple[...].
    results: list[Any] = []
    return_type = info.get_return_type()
    if not info.skip_return() and return_type.get_tag() != _VOID:
        annotation = annotation_for_type(return_type, context)
        if info.may_return_null():
            annotation = annotation | None
        results.append(annotation)
    for index, arg in enumerate(args):
        if index in skip or arg.get_direction() not in (_DIR_OUT, _DIR_INOUT):
            continue
        annotation = annotation_for_type(arg.get_type_info(), context)
        if arg.may_be_null():
            annotation = annotation | None
        results.append(annotation)

    if not results:
        return_annotation: Any = None
    elif len(results) == 1:
        return_annotation = results[0]
    else:
        return_annotation = tuple[tuple(results)]  # type: ignore[misc]

    return inspect.Signature(parameters, return_annotation=return_annotation)


def callable_signature(gimeta: Any) -> inspect.Signature:
    """Lazily build and cache the Signature for a GI callable wrapper.

    Backs the `__signature__` of `method.Function` and `method._GICallable`; the
    result is memoised on the wrapper's `gimeta` so repeated `inspect.signature()`
    calls are cheap. `gimeta.has_self` selects the leading `self` parameter for
    instance methods and vfuncs.
    """
    if gimeta.signature is None:
        gimeta.signature = build_signature(
            gimeta.info,
            has_self=gimeta.has_self,
            context=gimeta.namespace,
            keyword_only_after=getattr(gimeta, "keyword_only_after", None),
        )
    return cast("inspect.Signature", gimeta.signature)
