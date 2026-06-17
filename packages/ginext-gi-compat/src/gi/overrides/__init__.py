# Copyright 2026 Johan Dahlin
#
# Adapted from pygobject gi/overrides/__init__.py for use with ginext.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

from __future__ import annotations

import functools
import importlib
import sys
import types
from typing import Any, Callable

import gi.repository

# support overrides in different directories than our gi module
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)


class OverridesProxyModule(types.ModuleType):
    """Wraps an introspection module and contains all overrides."""

    __slots__ = ("_introspection_module",)

    def __init__(self, introspection_module: object) -> None:
        super().__init__(introspection_module.__name__)  # type: ignore[attr-defined]
        self._introspection_module = introspection_module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._introspection_module, name)

    def __delattr__(self, name: str) -> None:
        found = False
        if name in self.__dict__:
            del self.__dict__[name]
            found = True
        try:
            delattr(self._introspection_module, name)  # type: ignore[arg-type]
        except AttributeError:
            if not found:
                raise

    def __dir__(self) -> list[str]:
        result = set(super().__dir__())
        result.update(dir(self._introspection_module))
        return sorted(result)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self._introspection_module!r}>"


def load_overrides(introspection_module: object) -> object:
    """Load overrides for an introspection module.

    Returns a proxy module that includes all override symbols, or the
    original module if no overrides exist.
    """
    namespace = introspection_module.__name__.rsplit(".", 1)[-1]  # type: ignore[attr-defined]
    module_key = "gi.repository." + namespace

    has_old = module_key in sys.modules
    old_module = sys.modules.get(module_key)

    proxy = OverridesProxyModule(introspection_module)
    sys.modules[module_key] = proxy

    try:
        from ..importer import modules
    except ImportError:
        modules = {}  # type: ignore[assignment]

    modules[namespace] = proxy

    try:
        override_package_name = "gi.overrides." + namespace
        spec = importlib.util.find_spec(override_package_name)
        override_loader = spec.loader if spec is not None else None

        if override_loader is None:
            return introspection_module

        override_mod = importlib.import_module(override_package_name)

    finally:
        modules.pop(namespace, None)
        sys.modules.pop(module_key, None)
        if has_old:
            sys.modules[module_key] = old_module

    proxy._overrides_module = proxy  # type: ignore[attr-defined]

    override_all = []
    if hasattr(override_mod, "__all__"):
        override_all = override_mod.__all__

    for var in override_all:
        try:
            item = getattr(override_mod, var)
        except (AttributeError, TypeError):
            continue
        setattr(proxy, var, item)

    return proxy


def override(type_: Any) -> Any:
    """Decorator for registering an override class or function."""
    from gi._gi import CallableInfo
    from gi._constants import TYPE_NONE, TYPE_INVALID

    if isinstance(type_, CallableInfo):
        func = type_
        namespace = func.__module__.rsplit(".", 1)[-1]
        module = sys.modules["gi.repository." + namespace]

        def wrapper(func: Any) -> Any:
            setattr(module, func.__name__, func)
            return func

        return wrapper

    if isinstance(type_, types.FunctionType):
        raise TypeError(f"func must be a gi function, got {type_}")

    try:
        info = type_.__info__
    except AttributeError:
        raise TypeError(
            f"Can not override a type {type_.__name__}, which is not in a gobject "
            "introspection typelib"
        )

    if not type_.__module__.startswith("gi.overrides"):
        raise KeyError(
            "You have tried override outside of the overrides module. "
            f"This is not allowed ({type_}, {type_.__module__})"
        )

    g_type = info.get_g_type()
    assert g_type != TYPE_NONE
    if g_type != TYPE_INVALID:
        g_type.pytype = type_

    namespace = type_.__module__.rsplit(".", 1)[-1]
    module = sys.modules["gi.repository." + namespace]
    setattr(module, type_.__name__, type_)

    return type_


def strip_boolean_result(
    method: Callable[..., Any],
    exc_type: type | None = None,
    exc_str: str | None = None,
    fail_ret: object = None,
) -> Callable[..., Any]:
    """Translate method's return value for stripping off success flag."""

    @functools.wraps(method)
    def wrapped(*args: object, **kwargs: object) -> object:
        ret = method(*args, **kwargs)
        if ret[0]:
            if len(ret) == 2:
                return ret[1]
            return ret[1:]
        if exc_type:
            raise exc_type(exc_str or "call failed")
        return fail_ret

    return wrapped


def wrap_list_store_sort_func(func: Callable[..., Any]) -> Callable[..., Any]:
    from gi._gi import pygobject_new_full

    def wrap(a: object, b: object, *user_data: object) -> object:
        a = pygobject_new_full(a, False)
        b = pygobject_new_full(b, False)
        return func(a, b, *user_data)

    return wrap


def wrap_list_store_equal_func(func: Callable[..., Any]) -> Callable[..., Any]:
    from gi._gi import pygobject_new_full

    def wrap(a: object, b: object, *user_data: object) -> object:
        a = pygobject_new_full(a, False)
        b = pygobject_new_full(b, False)
        return func(a, b, *user_data)

    return wrap


def __getattr__(name: str) -> types.ModuleType:
    module_name = f"{__name__}.{name}"
    existing = sys.modules.get(module_name)
    if isinstance(existing, types.ModuleType):
        return existing

    try:
        module = importlib.import_module(module_name)
        globals()[name] = module
        return module
    except ModuleNotFoundError:
        pass

    repository_module = getattr(gi.repository, name)
    module = types.ModuleType(module_name)
    _module: Any = module
    _module.__all__ = []
    setattr(module, name, repository_module)
    sys.modules[module_name] = module
    globals()[name] = module
    return module


__all__ = [
    "OverridesProxyModule",
    "load_overrides",
    "override",
    "strip_boolean_result",
    "wrap_list_store_equal_func",
    "wrap_list_store_sort_func",
]
