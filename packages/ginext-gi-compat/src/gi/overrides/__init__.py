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
import warnings
from typing import Any, Callable

import gi.repository
from gi import PyGIDeprecationWarning

# support overrides in different directories than our gi module
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)


# namespace -> list of (attr, replacement)
_deprecated_attrs: dict[str, list[tuple[str, str]]] = {}


class OverridesProxyModule(types.ModuleType):
    """Wraps an introspection module and contains all overrides."""

    __slots__ = ("_deprecations", "_introspection_module")

    def __init__(self, introspection_module: object) -> None:
        super().__init__(introspection_module.__name__)  # type: ignore[attr-defined]
        self._introspection_module = introspection_module
        self._deprecations: dict[str, tuple[object, str]] = {}

    def __getattr__(self, name: str) -> Any:
        if name in self._deprecations:
            value, warning = self._deprecations[name]
            warnings.warn(warning, stacklevel=2)
            return value
        return getattr(self._introspection_module, name)

    def __delattr__(self, name: str) -> None:
        found = False
        if name in self.__dict__:
            del self.__dict__[name]
            found = True
        if name in self._deprecations:
            del self._deprecations[name]
            found = True
        try:
            delattr(self._introspection_module, name)  # type: ignore[arg-type]
        except AttributeError:
            if not found:
                raise

    def __dir__(self) -> list[str]:
        result = set(super().__dir__())
        result.update(self._deprecations.keys())
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
        except AttributeError, TypeError:
            continue
        setattr(proxy, var, item)

    for attr, replacement in _deprecated_attrs.pop(namespace, []):
        try:
            value = getattr(proxy, attr)
        except AttributeError:
            raise AssertionError(
                f"{attr} was set deprecated but wasn't added to __all__"
            )
        delattr(proxy, attr)
        proxy._deprecations[attr] = (
            value,
            PyGIDeprecationWarning(
                f"{namespace}.{attr} is deprecated; use {replacement} instead"
            ),
        )

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


overridefunc = override
"""Deprecated"""


def deprecated(fn: Callable[..., Any], replacement: str) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapped(*args: object, **kwargs: object) -> object:
        warnings.warn(
            f"{fn.__name__} is deprecated; use {replacement} instead",
            PyGIDeprecationWarning,
            stacklevel=2,
        )
        return fn(*args, **kwargs)

    return wrapped


def deprecated_attr(namespace: str, attr: str, replacement: str) -> None:
    """Marks a module level attribute as deprecated."""
    _deprecated_attrs.setdefault(namespace, []).append((attr, replacement))


def deprecated_init(
    super_init_func: Callable[..., Any],
    arg_names: tuple[str, ...] | None = None,
    *,
    ignore: tuple[str, ...] = (),
    deprecated_aliases: dict[str, str] | None = None,
    deprecated_defaults: dict[str, object] | None = None,
    category: type = PyGIDeprecationWarning,
    stacklevel: int = 2,
) -> Callable[..., Any]:
    _arg_names = arg_names or ()
    _aliases = deprecated_aliases or {}
    _defaults = deprecated_defaults or {}

    def new_init(self: object, *args: object, **kwargs: object) -> None:
        if args:
            warnings.warn(
                "Using positional arguments with the GObject constructor has been deprecated. "
                f'Please specify keyword(s) for "{", ".join(_arg_names[: len(args)])}" or use a class specific constructor. '
                "See: https://wiki.gnome.org/Projects/PyGObject/InitializerDeprecations",
                category,
                stacklevel=stacklevel,
            )
            new_kwargs: dict[str, object] = dict(zip(_arg_names, args))
        else:
            new_kwargs = {}
        new_kwargs.update(kwargs)

        aliases_used = []
        for key, alias in _aliases.items():
            if alias in new_kwargs:
                new_kwargs[key] = new_kwargs.pop(alias)
                aliases_used.append(key)

        if aliases_used:
            warnings.warn(
                'The keyword(s) "{}" have been deprecated in favor of "{}" respectively. '
                "See: https://wiki.gnome.org/Projects/PyGObject/InitializerDeprecations".format(
                    ", ".join(_aliases[k] for k in sorted(aliases_used)),
                    ", ".join(sorted(aliases_used)),
                ),
                category,
                stacklevel=stacklevel,
            )

        defaults_used = []
        for key in _defaults:
            if key not in new_kwargs:
                new_kwargs[key] = _defaults[key]
                defaults_used.append(key)

        if defaults_used:
            warnings.warn(
                "Initializer is relying on deprecated non-standard "
                "defaults. Please update to explicitly use: {} "
                "See: https://wiki.gnome.org/Projects/PyGObject/InitializerDeprecations".format(
                    ", ".join(f"{k}={_defaults[k]}" for k in sorted(defaults_used))
                ),
                category,
                stacklevel=stacklevel,
            )

        for key in ignore:
            new_kwargs.pop(key, None)

        return super_init_func(self, **new_kwargs)

    return new_init


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
    "deprecated",
    "deprecated_attr",
    "deprecated_init",
    "load_overrides",
    "override",
    "overridefunc",
    "strip_boolean_result",
    "wrap_list_store_equal_func",
    "wrap_list_store_sort_func",
]
