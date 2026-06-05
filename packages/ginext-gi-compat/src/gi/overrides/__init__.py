# Copyright 2026 Johan Dahlin
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

from __future__ import annotations

import functools
import sys
import types
import warnings
from typing import Any, Callable

import gi.repository
from gi import PyGIDeprecationWarning


def override(cls: type) -> type:
    return cls


def load_overrides(module: object) -> object:
    return module


def deprecated_init(
    func: Callable[..., Any],
    arg_names: tuple[str, ...] | None = None,
    *,
    ignore: tuple[str, ...] = (),
    deprecated_aliases: dict[str, str] | None = None,
    deprecated_defaults: dict[str, object] | None = None,
):
    @functools.wraps(func)
    def wrapper(*args: object, **kwargs: object) -> object:
        if arg_names and len(args) > 1:
            values = dict(zip(arg_names, args[1:], strict=False))
            values.update(kwargs)
            kwargs = {k: v for k, v in values.items() if k not in ignore}
            warnings.warn(
                "Using positional arguments is deprecated; use keyword arguments "
                + ", ".join(arg_names),
                PyGIDeprecationWarning,
                stacklevel=2,
            )
            return func(args[0], **kwargs)

        if deprecated_aliases:
            used_aliases = [
                alias for _name, alias in deprecated_aliases.items() if alias in kwargs
            ]
            if used_aliases:
                for name, alias in deprecated_aliases.items():
                    if alias in kwargs:
                        kwargs[name] = kwargs.pop(alias)
                warnings.warn(
                    'Using keyword aliases "%s" is deprecated; use "%s" respectively'
                    % (
                        ", ".join(used_aliases),
                        ", ".join(
                            name
                            for name, alias in deprecated_aliases.items()
                            if alias in used_aliases
                        ),
                    ),
                    PyGIDeprecationWarning,
                    stacklevel=2,
                )

        if deprecated_defaults:
            missing = {
                name: value
                for name, value in deprecated_defaults.items()
                if name not in kwargs
            }
            if missing:
                kwargs.update(missing)
                warnings.warn(
                    "relying on deprecated non-standard defaults is deprecated; "
                    "explicitly use: "
                    + ", ".join(f"{name}={value!r}" for name, value in missing.items()),
                    PyGIDeprecationWarning,
                    stacklevel=2,
                )
        return func(*args, **kwargs)

    return wrapper


def __getattr__(name: str) -> types.ModuleType:
    import importlib

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


__all__ = ["deprecated_init", "load_overrides", "override"]
