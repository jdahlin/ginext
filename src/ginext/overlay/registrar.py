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

import builtins as _builtins
import functools
import inspect
from typing import Any, Literal, TYPE_CHECKING, cast

from .. import private
from . import state
from .callbacks import callback_arg_types_for_body, callback_types
from .types import (
    AliasOverlay,
    BodyOverlay,
    ClassBasesOverlay,
    ConstantOverlay,
    ConstructorOverlay,
    DeprecatedOverlay,
    FirstAccessHook,
    ModuleEntry,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ginext.namespace import Namespace
    from ginext.GIRepository import CallableInfo


_MISSING = object()


def _same_overlay_base(left: type | str, right: type | str) -> bool:
    if left == right:
        return True
    if isinstance(left, str) or isinstance(right, str):
        return False
    return getattr(left, "__module__", None) == getattr(
        right, "__module__", None
    ) and getattr(left, "__qualname__", None) == getattr(right, "__qualname__", None)


def _same_overlay_bases(
    left: tuple[type | str, ...], right: tuple[type | str, ...]
) -> bool:
    return len(left) == len(right) and all(
        _same_overlay_base(left_base, right_base)
        for left_base, right_base in zip(left, right, strict=False)
    )


class OverlayRegistrar:
    """Namespace-scoped overlay registration handle.

    Decorators register callables; imperative methods register
    non-callables (aliases, constants, bases, lifecycle hooks).
    The decorated function's ``__name__`` is the overlay name.
    """

    __slots__ = ("_namespace", "_ns_name")

    def __init__(self, namespace: Namespace) -> None:
        self._namespace = namespace
        self._ns_name = namespace.__name__

    def replace[**P, R](self, fn: Callable[P, R]) -> Callable[P, R]:
        self._check_typelib_presence(getattr(fn, "__name__", ""), expect_present=True)
        entry = self._body_overlay_maybe_with_fn(fn)
        self._set_module(getattr(fn, "__name__", ""), entry)
        return entry.body

    def add[**P, R](
        self,
        fn_or_target: Callable[P, R] | str,
    ) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
        if isinstance(fn_or_target, str):
            target = fn_or_target

            def decorator(fn: Callable[P, R]) -> Callable[P, R]:
                self._check_typelib_presence(
                    getattr(fn, "__name__", ""), expect_present=False
                )
                qualified_name = (
                    target if "." in target else getattr(fn, "__name__", "")
                )
                if not qualified_name.startswith(f"{self._ns_name}."):
                    qualified_name = f"{self._ns_name}.{qualified_name}"
                cached_fn = private.synthetic_callable(qualified_name)
                entry = self._body_overlay_maybe_with_fn(fn, cached_fn=cached_fn)
                self._set_module(getattr(fn, "__name__", ""), entry)
                return entry.body

            return decorator

        fn = fn_or_target
        self._check_typelib_presence(getattr(fn, "__name__", ""), expect_present=False)
        entry = self._body_overlay_maybe_with_fn(fn)
        self._set_module(getattr(fn, "__name__", ""), entry)
        return entry.body

    def method[**P, R](
        self,
        class_name: str,
        *,
        name: str | None = None,
        as_staticmethod: bool = False,
        as_classmethod: bool = False,
        **kwargs: object,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        as_staticmethod, as_classmethod = self._normalize_method_flags(
            as_staticmethod=as_staticmethod,
            as_classmethod=as_classmethod,
            kwargs=kwargs,
        )

        def decorator(fn: Callable[P, R]) -> Callable[P, R]:
            entry = self._body_overlay_maybe_with_fn(
                fn,
                as_staticmethod=as_staticmethod,
                as_classmethod=as_classmethod,
                method_inject=True,
            )
            method_name = name if name is not None else getattr(fn, "__name__", "")
            self._set_class_method(class_name, method_name, entry)
            return fn

        return decorator

    def _normalize_method_flags(
        self,
        *,
        as_staticmethod: bool = False,
        as_classmethod: bool = False,
        kwargs: dict[str, object],
    ) -> tuple[bool, bool]:
        static_flag = kwargs.pop("staticmethod", _MISSING)
        class_flag = kwargs.pop("classmethod", _MISSING)
        if kwargs:
            raise TypeError(f"unexpected keyword argument {next(iter(kwargs))!r}")
        if static_flag is not _MISSING:
            if as_staticmethod:
                raise TypeError("staticmethod must not be passed twice")
            as_staticmethod = bool(static_flag)
        if class_flag is not _MISSING:
            if as_classmethod:
                raise TypeError("classmethod must not be passed twice")
            as_classmethod = bool(class_flag)
        return as_staticmethod, as_classmethod

    def property[**P, R](
        self,
        class_name: str,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        def decorator(fn: Callable[P, R]) -> Callable[P, R]:
            entry = self._body_overlay(
                fn,
                name=getattr(fn, "__name__", ""),
                body=_builtins.property(cast("Callable[[Any], Any]", fn)),
                as_descriptor=True,
            )
            self._set_class_method(class_name, getattr(fn, "__name__", ""), entry)
            return fn

        return decorator

    def callback_types[**P, R](
        self,
        parameter_name: str,
        *arg_types: type | str,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        return callback_types(parameter_name, *arg_types)

    def alias(self, source: str, target: str) -> None:
        self._set_module(target, AliasOverlay(name=target, target_path=source))

    def constant(self, name: str, value: object) -> None:
        self._set_module(name, ConstantOverlay(name=name, value=value))

    def constants(self, mapping: dict[str, object]) -> None:
        for k, v in mapping.items():
            self.constant(k, v)

    def deprecated(self, name: str, value: object, replacement: str) -> None:
        # Unlike the module-level overlays (registered once at import), this is
        # called from apply_to_namespace, which re-runs whenever the overlay
        # load guard is reset (e.g. reset_caches between tests) while the global
        # module-overlay registry persists. Re-register idempotently, binding
        # the live namespace's value rather than raising on the stale entry.
        entry = DeprecatedOverlay(name=name, value=value, replacement=replacement)
        key = (self._ns_name, name)
        state.module_overlays[key] = entry
        state.deprecated_entries[key] = entry

    def bases(self, class_name: str, bases: Sequence[type | str]) -> None:
        key = (self._ns_name, class_name)
        new_entry = ClassBasesOverlay(
            qname=f"{self._ns_name}.{class_name}",
            bases=tuple(bases),
        )
        existing = state.class_bases_overlays.get(key)
        if existing is not None:
            # Re-registering the same bases is idempotent (e.g. after
            # reset_caches() re-loads the overlay module).  Conflicting bases
            # are still an error.
            if not _same_overlay_bases(existing.bases, new_entry.bases):
                raise ValueError(
                    f"bases overlay already set for {self._ns_name}.{class_name}"
                )
            return
        state.class_bases_overlays[key] = new_entry

    def constructor[**P, R](
        self,
        class_name: str,
        *,
        init: Callable[..., Any] | None = None,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Register a pygobject-compat constructor (``__new__``) for a class.

        The decorated function is installed as ``Class.__new__`` (a static
        method) eagerly at class-build time, with an optional ``init`` as
        ``__init__`` (defaulting to a no-op). It is called as ``new(cls, ...)``;
        while it runs the overlay module's namespace global is bound to ``cls``'s
        own (per-profile) namespace, so nested constructor calls resolve to the
        right profile. Use this instead of hand-wiring ``Class.__new__`` in an
        ``apply_to_namespace`` hook.
        """

        def decorator(fn: Callable[P, R]) -> Callable[P, R]:
            key = (self._ns_name, class_name)
            entry = ConstructorOverlay(
                ns=self._ns_name, class_name=class_name, new=fn, init=init
            )
            existing = state.constructor_overlays.get(key)
            if existing is not None and existing.new is not fn:
                raise ValueError(
                    f"constructor overlay already set for {self._ns_name}.{class_name}"
                )
            state.constructor_overlays[key] = entry
            return fn

        return decorator

    def hide_attribute(self, name: str) -> None:
        self._check_typelib_presence(name, expect_present=True)
        state.hidden_attribute_names.setdefault(self._ns_name, set()).add(name)

    def defaults(
        self, class_name: str, method_name: str, **param_defaults: object
    ) -> None:
        """Declare default values for a method's arguments.

        A caller may then omit those arguments; the default is supplied when
        the parameter is not passed positionally or by keyword. Trailing
        nullable arguments (e.g. ``cancellable``) are already omittable, so
        this is mainly for non-nullable middle arguments such as ``flags`` and
        ``io_priority``.
        """
        if not param_defaults:
            raise TypeError("defaults() requires at least one param=value")
        per_class = state.method_arg_defaults.setdefault(
            (self._ns_name, class_name), {}
        )
        per_class.setdefault(method_name, {}).update(param_defaults)

    def async_result(self, class_name: str, method_name: str, *out_names: str) -> None:
        """Shape an async method's awaited result as a ``NamedReturn``.

        ``out_names`` has one entry per item the ``*_finish`` returns (``""``
        for the bare return value), so callers can read OUT values by name::

            overlay.async_result("DBusProxy", "call_with_unix_fd_list",
                                  "", "out_fd_list")
            result = await proxy.call_with_unix_fd_list(...)
            fd_list = result.out_fd_list
        """
        state.async_result_names[(self._ns_name, class_name, method_name)] = out_names

    def on_first_access(
        self,
        callback: Callable[[], Any],
        *,
        env_gate: str | None = None,
        on_error: Literal["raise", "warn"] = "raise",
    ) -> None:
        cfg = state.lifecycle_for(self._ns_name)
        cfg.first_access.append(
            FirstAccessHook(
                callback=callback,
                env_gate=env_gate,
                on_error=on_error,
            )
        )

    def _check_typelib_presence(self, name: str, *, expect_present: bool) -> None:
        try:
            self._find_typelib_member(name)
            present = True
        except AttributeError:
            present = False
        if expect_present and not present:
            raise ValueError(
                f"@{self._ns_name}.overlay.replace: "
                f"{self._ns_name}.{name} not in typelib — use .add for new names"
            )
        if not expect_present and present:
            raise ValueError(
                f"@{self._ns_name}.overlay.add: "
                f"{self._ns_name}.{name} already exists in typelib — use .replace"
            )

    def _find_typelib_member(self, name: str) -> tuple[str, CallableInfo]:
        # The registrar resolves callable (function/method) members for overlays,
        # so the BaseInfo half is a CallableInfo.
        return cast(
            "tuple[str, CallableInfo]",
            private.namespace_find(self._ns_name, self._namespace._version, name),
        )

    def _set_module(self, name: str, entry: ModuleEntry) -> None:
        key = (self._ns_name, name)
        if key in state.module_overlays:
            # Idempotent: two bootstrap instances share state but have separate
            # module caches; re-registration is harmless.
            return
        state.module_overlays[key] = entry

    def _set_class_method(self, class_name: str, name: str, entry: BodyOverlay) -> None:
        from .install import maybe_apply_class_overlays_now

        key = (self._ns_name, class_name)
        methods = state.class_method_overlays.setdefault(key, {})
        if name in methods:
            # Idempotent: two bootstrap instances share state but have separate
            # module caches; re-registration of the same overlay is harmless.
            return
        methods[name] = entry
        maybe_apply_class_overlays_now(self._ns_name, class_name)

    def _body_overlay[**P, R](
        self,
        fn: Callable[P, R],
        *,
        name: str | None = None,
        body: object | None = None,
        as_staticmethod: bool = False,
        as_classmethod: bool = False,
        as_descriptor: bool = False,
        inject_fn: bool = False,
    ) -> BodyOverlay:
        return BodyOverlay(
            name=name or cast("str", getattr(fn, "__name__", "")),
            body=cast("Any", body or fn),
            as_staticmethod=as_staticmethod,
            as_classmethod=as_classmethod,
            as_descriptor=as_descriptor,
            inject_fn=inject_fn,
            callback_arg_types=callback_arg_types_for_body(fn),
        )

    def _body_overlay_maybe_with_fn[**P, R](
        self,
        fn: Callable[P, R],
        *,
        name: str | None = None,
        cached_fn: object | None = None,
        as_staticmethod: bool = False,
        as_classmethod: bool = False,
        method_inject: bool = False,
    ) -> BodyOverlay:
        overlay_name = name or cast("str", getattr(fn, "__name__", ""))
        signature = inspect.signature(fn)
        parameters = list(signature.parameters.values())
        inject_fn = bool(parameters and parameters[0].name == "fn")
        if not inject_fn:
            return self._body_overlay(
                fn,
                name=overlay_name,
                as_staticmethod=as_staticmethod,
                as_classmethod=as_classmethod,
            )

        if method_inject:
            return self._body_overlay(
                fn,
                name=overlay_name,
                as_staticmethod=as_staticmethod,
                as_classmethod=as_classmethod,
                inject_fn=True,
            )

        if cached_fn is None:
            _, info = self._find_typelib_member(overlay_name)
            cached_fn = _CachedTypelibCallable(
                self._namespace,
                info,
                f"{self._ns_name}.{overlay_name}",
                has_self=False,
            )

        @functools.wraps(fn)
        def wrapper(*args: object, **kwargs: object) -> object:
            return cast("Any", fn)(cached_fn, *args, **kwargs)

        if parameters:
            _wrapper: Any = wrapper
            _wrapper.__signature__ = signature.replace(parameters=parameters[1:])

        return self._body_overlay(
            fn,
            name=overlay_name,
            body=wrapper,
            as_staticmethod=as_staticmethod,
            as_classmethod=as_classmethod,
        )


class _CachedTypelibCallable:
    __slots__ = ("_descriptor", "_has_self", "_info", "_namespace", "_qualified_name")

    def __init__(
        self,
        namespace: Namespace,
        info: CallableInfo,
        qualified_name: str,
        *,
        has_self: bool,
    ) -> None:
        self._namespace = namespace
        self._info = info
        self._qualified_name = qualified_name
        self._has_self = has_self
        self._descriptor: object | None = None

    def __call__(self, *args: object, **kwargs: object) -> object:
        descriptor = self._descriptor
        if descriptor is None:
            descriptor = private.build_callable_descriptor(
                self._info,
                self._qualified_name,
                self._has_self,
                self._namespace,
            )
            self._descriptor = descriptor
        return private.invoke_callable_descriptor(descriptor, args, kwargs)
