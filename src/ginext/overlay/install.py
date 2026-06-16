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
import functools as _functools
import inspect as _inspect
import os as _os
import sys as _sys
import warnings
from typing import Any, Callable, TYPE_CHECKING, cast

from . import state
from .types import (
    AliasOverlay,
    BodyOverlay,
    ConstantOverlay,
    DeprecatedOverlay,
    ModuleEntry,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from ginext.namespace import Namespace


def module_overlay_for(ns: str, name: str) -> ModuleEntry | None:
    return state.module_overlays.get((ns, name))


class _DeprecationsProxy:
    """Mutable dict-like view over a namespace's deprecated entries.

    Exposes the same pygobject-compat interface: ``ns._deprecations[name]``
    returns ``(value, replacement)``; assigning restores a deleted entry.
    """

    __slots__ = ("_ns_name",)

    def __init__(self, ns_name: str) -> None:
        self._ns_name = ns_name

    def __getitem__(self, name: str) -> tuple[object, str]:
        entry = state.deprecated_entries.get((self._ns_name, name))
        if entry is None:
            raise KeyError(name)
        return (entry.value, entry.replacement)

    def __setitem__(self, name: str, value: tuple[object, str]) -> None:
        val, replacement = value
        entry = DeprecatedOverlay(name=name, value=val, replacement=replacement)
        key = (self._ns_name, name)
        state.deprecated_entries[key] = entry
        state.module_overlays[key] = entry

    def __delitem__(self, name: str) -> None:
        key = (self._ns_name, name)
        state.deprecated_entries.pop(key, None)
        state.module_overlays.pop(key, None)

    def __contains__(self, name: object) -> bool:
        return (self._ns_name, name) in state.deprecated_entries

    def __iter__(self) -> Iterator[str]:
        ns = self._ns_name
        for ns2, name in state.deprecated_entries:
            if ns2 == ns:
                yield name

    def __len__(self) -> int:
        ns = self._ns_name
        return sum(1 for (ns2, _) in state.deprecated_entries if ns2 == ns)


def deprecations_proxy_for(ns_name: str) -> _DeprecationsProxy:
    return _DeprecationsProxy(ns_name)


def class_method_overlays_for(ns: str, class_name: str) -> dict[str, BodyOverlay]:
    return state.class_method_overlays.get((ns, class_name), {})


def async_result_names_for(
    ns: str, class_name: str, method_name: str
) -> tuple[str, ...] | None:
    return state.async_result_names.get((ns, class_name, method_name))


def method_arg_defaults_for(
    ns: str, class_name: str, method_name: str
) -> dict[str, object]:
    return state.method_arg_defaults.get((ns, class_name), {}).get(method_name, {})


def keyword_only_after_for(ns: str, owner: str, method_name: str) -> int | None:
    """Cutoff index past which a callable's visible args are keyword-only.

    ``owner`` is the class name, or "" for a module-level function. Returns
    None when the callable has no keyword-only overlay.
    """
    return state.keyword_only_args.get((ns, owner), {}).get(method_name)


def class_bases_overlay_for(
    ns: str, class_name: str, profile: object = None
) -> tuple[type, ...]:
    entry = state.class_bases_overlays.get((ns, class_name))
    if entry is None:
        return ()
    return tuple(
        _resolve_dotted_type(b, profile=profile) if isinstance(b, str) else b
        for b in entry.bases
    )


def run_first_access(ns: str) -> None:
    cfg = state.lifecycle.get(ns)
    if cfg is None or cfg.first_access_ran or cfg.first_access_running:
        return
    cfg.first_access_running = True
    try:
        for hook in cfg.first_access:
            if hook.env_gate is not None:
                value = _os.environ.get(hook.env_gate, "1")
                if value.lower() in {"0", "false", "no"}:
                    continue
            try:
                hook.callback()
            except Exception as exc:
                if hook.on_error == "raise":
                    raise
                name = getattr(hook.callback, "__name__", repr(hook.callback))
                print(
                    f"ginext: first-access hook {ns}.{name} failed: {exc}",
                    file=_sys.stderr,
                )
        # Mark ran only after every hook ran (or warned). A raising
        # hook leaves it False so a later attribute access retries —
        # the caller chose on_error="raise" so they're aware the
        # failure was real.
        cfg.first_access_ran = True
    finally:
        cfg.first_access_running = False


def module_overlay_names(ns: str) -> list[str]:
    return [name for (n, name) in state.module_overlays if n == ns]


def hidden_attribute_names_for(ns: str) -> frozenset[str]:
    return frozenset(state.hidden_attribute_names.get(ns, ()))


def is_attribute_hidden(ns: str, name: str) -> bool:
    return name in state.hidden_attribute_names.get(ns, ())


def is_class_method_hidden(ns: str, class_name: str, name: str) -> bool:
    return name in state.hidden_class_method_names.get((ns, class_name), ())


def install_module_overlay(
    namespace_module: Namespace,
    name: str,
    entry: ModuleEntry,
) -> Any:
    if isinstance(entry, ConstantOverlay):
        return entry.value
    if isinstance(entry, AliasOverlay):
        return _resolve_attribute_path(namespace_module, entry.target_path)
    if isinstance(entry, DeprecatedOverlay):
        try:
            from gi import PyGIDeprecationWarning as _W
        except ImportError:
            _W = DeprecationWarning  # type: ignore[assignment, misc]
        ns_name = getattr(namespace_module, "_name", name)
        with warnings.catch_warnings():
            warnings.simplefilter("always", _W)
            warnings.warn(
                f"{ns_name}.{name} is deprecated; use {entry.replacement} instead",
                _W,
                stacklevel=3,
            )
        return entry.value
    return entry.body


def _noop_init(self: object, *args: object, **kwargs: object) -> None:
    # pygobject-compat constructors do all their work in __new__; __init__ is a
    # no-op (the C base __init__ would reject the compat kwargs).
    pass


def install_class_constructor(cls: type, ns: str, class_name: str) -> None:
    entry = state.constructor_overlays.get((ns, class_name))
    if entry is None:
        return
    new_fn = entry.new
    ns_name = entry.ns
    fn_globals = getattr(new_fn, "__globals__", None)

    def __new__(cls: type, *args: object, **kwargs: object) -> object:
        # Bind the overlay module's namespace global (e.g. `GLib`) to cls's own
        # per-profile namespace for the call, so nested constructor calls in
        # new_fn resolve to the right profile (compat vs native).
        if fn_globals is None:
            return new_fn(cls, *args, **kwargs)
        sentinel = object()
        saved = fn_globals.get(ns_name, sentinel)
        fn_globals[ns_name] = cast("Any", cls).gimeta.namespace.load_namespace()
        try:
            return new_fn(cls, *args, **kwargs)
        finally:
            if saved is sentinel:
                fn_globals.pop(ns_name, None)
            else:
                fn_globals[ns_name] = saved

    __new__.__name__ = "__new__"
    typed_cls = cast("Any", cls)
    typed_cls.__new__ = staticmethod(__new__)
    typed_cls.__init__ = entry.init if entry.init is not None else _noop_init
    typed_cls._pygobject_compat_constructor = True


def install_class_overlay(cls: type, ns: str, class_name: str) -> None:
    install_class_constructor(cls, ns, class_name)
    methods = state.class_method_overlays.get((ns, class_name), {})
    if not methods:
        return
    for method_name, entry in methods.items():
        gimeta = getattr(cls, "gimeta", None)
        typelib_methods = getattr(gimeta, "typelib_methods", None)
        if typelib_methods is not None and method_name not in typelib_methods:
            existing = cls.__dict__.get(method_name)
            try:
                from ginext.classbuild import install_method_for_class

                found = install_method_for_class(cls, method_name)
                if found is None:
                    from ginext.record import install_method_for_record_class

                    found = install_method_for_record_class(
                        cast("Any", cls), method_name
                    )
            except ImportError:
                # Reached when applying overlays during bootstrap — e.g. installing
                # the foundational GObject.Object overlays at creation, before
                # classbuild has finished importing. A method that can't be resolved
                # through classbuild/record is not a typelib method, so treat it as a
                # plain overlay (the common case for the foundational dunders).
                found = None
            if found is not None:
                existing = cls.__dict__.get(method_name)
            # On the cached-by-gtype re-entry path, `existing` is the
            # overlay we previously installed; skip preservation so
            # typelib_methods never points back to the overlay.
            existing_body = existing
            if isinstance(existing, (classmethod, staticmethod)):
                existing_body = existing.__func__
            if existing is not None and existing_body is not entry.body:
                typelib_methods[method_name] = existing
        value: object = entry.body
        if entry.inject_fn:
            existing = _inspect.getattr_static(cls, method_name, None)
            value = _inject_typelib_fn(
                entry.body,
                cls,
                method_name,
                existing,
                as_staticmethod=entry.as_staticmethod,
                as_classmethod=entry.as_classmethod,
            )
        if entry.as_classmethod:
            value = classmethod(cast("Any", value))
        elif entry.as_staticmethod:
            value = staticmethod(cast("Any", value))
        setattr(cls, method_name, value)


def maybe_apply_class_overlays_now(ns: str, class_name: str) -> None:
    ginext_dict: dict[str, object] = vars(_sys.modules["ginext"])
    namespace = ginext_dict.get(ns)
    if namespace is None:
        return
    ns_dict: dict[str, object] = vars(namespace)
    cls = ns_dict.get(class_name)
    if cls is None or not isinstance(cls, type):
        return
    install_class_overlay(cls, ns, class_name)


def _inject_typelib_fn(
    body: Callable[..., Any],
    cls: Any,
    method_name: str,
    existing: object | None,
    *,
    as_staticmethod: bool,
    as_classmethod: bool,
) -> object:
    @_functools.wraps(body)
    def wrapper(*args: object, **kwargs: object) -> object:
        fn = cls.gimeta.typelib_methods.get(method_name)
        if fn is None:
            fn = existing
            if isinstance(fn, (classmethod, staticmethod)):
                fn = fn.__func__
        if fn is None:
            raise KeyError(method_name)
        return body(fn, *args, **kwargs)

    signature = _inspect.signature(body)
    parameters = list(signature.parameters.values())
    if parameters:
        _wrapper: Any = wrapper
        _wrapper.__signature__ = signature.replace(parameters=parameters[1:])
    return wrapper


def _resolve_attribute_path(root: object, path: str) -> Any:
    obj: Any = root
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _resolve_dotted_type(dotted: str, profile: object = None) -> type:
    head, _, tail = dotted.partition(".")
    if head == "builtins":
        return cast("type", getattr(_builtins, tail))
    ginext = _sys.modules["ginext"]
    if profile is not None and profile is not ginext.abi.NATIVE:
        version = ginext.defaults.resolve_version(head)
        assert version is not None
        target = ginext._load_namespace(head, version, profile=cast("Any", profile))
    else:
        target = getattr(ginext, head)
    return cast("type", _resolve_attribute_path(target, tail))
