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

import keyword
import inspect
import sys
import types
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from . import private

if TYPE_CHECKING:
    from typing import Protocol

    from .abi import NamespaceContext
    from .namespace import Namespace
    from ginext.GIRepository import CallableInfo, FunctionInfo

    class _SupportsObjclass(Protocol):
        __objclass__: type[object]


class PackedUserData(tuple[object, ...]):
    """Marker the C kwarg/user_data resolver attaches when multiple
    trailing positional args pack into the closure user_data slot. The
    callback trampoline in shims.c sees this subclass and unpacks the
    extras into separate callback positional args; bare tuples and other
    values pass through unchanged."""

    __slots__ = ()


from ginext import private as _private_hooks

_private_hooks.register_hook("packed_user_data_type", PackedUserData)


def _keyword_only_message(name: str, after: int, given: int) -> str:
    plural = "" if after == 1 else "s"
    return (
        f"{name}() takes {after} positional argument{plural} but {given} were "
        f"given (arguments past the first {after} are keyword-only)"
    )


def callable_name(info: CallableInfo) -> str:
    name: str = info.get_name().replace("-", "_")
    if keyword.iskeyword(name):
        return f"{name}_"
    return name


class Function:
    def __init__(self, context: NamespaceContext, info: FunctionInfo):
        name = callable_name(info)
        kw_only_after = sys.modules["ginext.overlay"].keyword_only_after_for(
            context.name, "", name
        )
        self.gimeta = types.SimpleNamespace(
            namespace=context,
            info=info,
            name=name,
            qualified_name=context.qualified_name(name),
            descriptor=None,
            has_self=False,
            signature=None,
            keyword_only_after=kw_only_after,
        )
        self.info = info
        self.__name__ = name
        self.__qualname__ = self.gimeta.qualified_name
        self.__module__ = context.module_name()
        self.__doc__ = None

    @property
    def __signature__(self) -> inspect.Signature:
        return _callable_signature(self.gimeta)

    def __call__(self, *args: object, **kwargs: object) -> object:
        descriptor = self.gimeta.descriptor
        if descriptor is None:
            descriptor = private.build_callable_descriptor(
                self.gimeta.info,
                self.gimeta.qualified_name,
                False,
                self.gimeta.namespace.load_namespace(),
            )
            self.gimeta.descriptor = descriptor
        after = self.gimeta.keyword_only_after
        if after is not None and len(args) > after:
            raise TypeError(_keyword_only_message(self.__name__, after, len(args)))
        return descriptor(*args, **kwargs)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Function):
            return bool(self.__qualname__ == other.__qualname__)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.__qualname__)

    def __repr__(self) -> str:
        return f"<function {self.__name__}>"


class FunctionBuilder:
    def __init__(self, context: NamespaceContext):
        self._context = context
        self.functions: dict[str, types.SimpleNamespace] = {}

    def build_function(self, info: FunctionInfo) -> object:
        name = callable_name(info)
        kw_only_after = sys.modules["ginext.overlay"].keyword_only_after_for(
            self._context.name, "", name
        )
        gimeta = types.SimpleNamespace(
            namespace=self._context,
            info=info,
            name=name,
            qualified_name=self._context.qualified_name(name),
            descriptor=None,
            has_self=False,
            signature=None,
            keyword_only_after=kw_only_after,
        )
        descriptor = private.build_callable_descriptor(
            info,
            gimeta.qualified_name,
            False,
            gimeta.namespace.load_namespace(),
        )
        gimeta.descriptor = descriptor
        self.functions[gimeta.name] = gimeta
        if kw_only_after is not None:

            def function(*args: object, **kwargs: object) -> object:
                if len(args) > kw_only_after:
                    raise TypeError(
                        _keyword_only_message(name, kw_only_after, len(args))
                    )
                return descriptor(*args, **kwargs)

            return GICallable(function, gimeta)
        return _attach_callable_metadata(
            descriptor,
            gimeta=gimeta,
            name=name,
            qualified_name=gimeta.qualified_name,
        )


class GICallable:
    """Callable descriptor for a GI method or static method.

    Behaves like the plain function it replaces — ``Cls.m`` is unbound,
    ``obj.m`` binds — but carries a lazy ``__signature__`` built from the
    callable's GI type info, which a plain function can't have lazily. Composes
    with ``staticmethod()``/``classmethod()`` wrapping (which classbuild applies
    for static methods and vfuncs): those bypass ``__get__``, so only the
    directly-stored instance-method form binds here.
    """

    __slots__ = (
        "_impl",
        "gimeta",
        "__name__",
        "__qualname__",
        "__objclass__",
        "__dict__",
    )

    def __init__(
        self, impl: Callable[..., object], gimeta: types.SimpleNamespace
    ) -> None:
        self._impl = impl
        self.gimeta = gimeta
        self.__name__ = gimeta.name
        self.__qualname__ = gimeta.qualified_name
        self.__module__ = _callable_module_name(gimeta)
        self.__doc__ = None
        self.__defaults__ = _callable_defaults(gimeta)
        self.__kwdefaults__ = _callable_kwdefaults(gimeta)
        self.__annotations__ = _callable_annotations(gimeta)
        self.__annotate__ = _callable_annotate(gimeta)
        self.__type_params__ = ()

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self._impl(*args, **kwargs)

    def __get__(self, obj: object, objtype: object = None) -> object:
        if obj is None:
            return self
        return types.MethodType(self, obj)

    @property
    def __signature__(self) -> inspect.Signature:
        return _callable_signature(self.gimeta)

    def __repr__(self) -> str:
        return f"<ginext method {self.__qualname__}>"


def _attach_callable_metadata(
    descriptor: private.CallableDescriptor,
    *,
    gimeta: types.SimpleNamespace,
    name: str,
    qualified_name: str,
) -> private.CallableDescriptor:
    descriptor.gimeta = gimeta
    descriptor.__name__ = name
    descriptor.__qualname__ = qualified_name
    descriptor.__module__ = _callable_module_name(gimeta)
    descriptor.__doc__ = None
    descriptor.__defaults__ = _callable_defaults(gimeta)
    descriptor.__kwdefaults__ = _callable_kwdefaults(gimeta)
    descriptor.__annotations__ = _callable_annotations(gimeta)
    descriptor.__annotate__ = _callable_annotate(gimeta)
    descriptor.__type_params__ = ()
    return descriptor


def attach_owner_metadata(method: object, owner: type[object]) -> object:
    try:
        cast("_SupportsObjclass", method).__objclass__ = owner
    except (AttributeError, TypeError):
        pass
    return method


def _callable_signature(gimeta: types.SimpleNamespace) -> inspect.Signature:
    from . import signature

    return signature.callable_signature(gimeta)


def _callable_module_name(gimeta: types.SimpleNamespace) -> str:
    return cast("str", gimeta.namespace.module_name())


def _callable_annotations(gimeta: types.SimpleNamespace) -> dict[str, object]:
    signature = _callable_signature(gimeta)
    annotations: dict[str, object] = {}
    for parameter in signature.parameters.values():
        if parameter.annotation is not inspect.Signature.empty:
            annotations[parameter.name] = cast("object", parameter.annotation)
    if signature.return_annotation is not inspect.Signature.empty:
        annotations["return"] = cast("object", signature.return_annotation)
    return annotations


def _callable_defaults(gimeta: types.SimpleNamespace) -> tuple[object, ...] | None:
    signature = _callable_signature(gimeta)
    defaults: list[object] = []
    collecting = False
    for parameter in signature.parameters.values():
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            continue
        if parameter.default is inspect.Signature.empty:
            if collecting:
                defaults.clear()
                collecting = False
            continue
        collecting = True
        defaults.append(cast("object", parameter.default))
    return tuple(defaults) if defaults else None


def _callable_kwdefaults(gimeta: types.SimpleNamespace) -> dict[str, object] | None:
    signature = _callable_signature(gimeta)
    defaults = {
        parameter.name: cast("object", parameter.default)
        for parameter in signature.parameters.values()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
        and parameter.default is not inspect.Signature.empty
    }
    return defaults or None


def _callable_annotate(
    gimeta: types.SimpleNamespace,
) -> Callable[[], dict[str, object]]:
    def annotate() -> dict[str, object]:
        return _callable_annotations(gimeta)

    annotate.__name__ = "__annotate__"
    annotate.__qualname__ = f"{gimeta.qualified_name}.__annotate__"
    annotate.__module__ = _callable_module_name(gimeta)
    return annotate


def make_method(
    namespace: Namespace,
    owner_name: str,
    info: CallableInfo,
    *,
    has_self: bool = True,
) -> Callable[..., object]:
    name = callable_name(info)
    qualified_name = f"{owner_name}.{name}"
    descriptor = private.build_callable_descriptor(
        info, qualified_name, has_self, namespace
    )

    ns_name, _, class_name = owner_name.rpartition(".")
    overlay = sys.modules["ginext.overlay"]
    arg_defaults = overlay.method_arg_defaults_for(ns_name, class_name, name)
    kw_only_after = overlay.keyword_only_after_for(ns_name, class_name, name)
    arg_index = (
        {pname: i for i, pname in enumerate(info.arg_names)} if arg_defaults else {}
    )

    def _apply_defaults(
        user_args: tuple[object, ...], kwargs: dict[str, object]
    ) -> None:
        # Supply a declared default for any parameter the caller left out, both
        # positionally and by keyword. The descriptor still rejects duplicate
        # or unknown arguments, so its error messages are preserved.
        for pname, default in arg_defaults.items():
            idx = arg_index.get(pname)
            if idx is None or idx < len(user_args) or pname in kwargs:
                continue
            kwargs[pname] = default

    def _check_keyword_only(user_args: tuple[object, ...]) -> None:
        if kw_only_after is not None and len(user_args) > kw_only_after:
            raise TypeError(_keyword_only_message(name, kw_only_after, len(user_args)))

    def method(self: object, *args: object, **kwargs: object) -> object:
        if arg_defaults:
            _apply_defaults(args, kwargs)
        _check_keyword_only(args)
        return descriptor(self, *args, **kwargs)

    def static_method(*args: object, **kwargs: object) -> object:
        if arg_defaults:
            _apply_defaults(args, kwargs)
        _check_keyword_only(args)
        return descriptor(*args, **kwargs)

    impl = method if has_self else static_method
    gimeta = types.SimpleNamespace(
        namespace=namespace.context,
        info=info,
        name=name,
        qualified_name=qualified_name,
        has_self=has_self,
        descriptor=descriptor,
        signature=None,
        keyword_only_after=kw_only_after,
    )
    if arg_defaults or kw_only_after is not None:
        return GICallable(impl, gimeta)
    return cast(
        "Callable[..., object]",
        _attach_callable_metadata(
            descriptor,
            gimeta=gimeta,
            name=name,
            qualified_name=qualified_name,
        ),
    )
