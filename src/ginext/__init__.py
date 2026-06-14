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

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import types

from . import abi
from . import defaults
from . import runtime as _runtime  # registers result_tuple_new_type hook
from .namespace import Namespace
from .overlay import load_overlay_module_for
from .signal.bound import Signal
from .signal.connection import SignalConnection, UnownedSignalHandlerWarning
from .signal.scoped import static_owner


class PyGIWarning(Warning):
    pass


class PyGIDeprecationWarning(DeprecationWarning):
    pass


_LOCAL_MODULES = {"aio", "cairo", "features", "gobject", "runtime"}


def _load_local_module(name: str) -> types.ModuleType:
    module_name = f"{__name__}.{name}"
    try:
        module = importlib.import_module(f".{name}", __name__)
    except ModuleNotFoundError:
        path = Path(__file__).resolve().with_name(f"{name}.py")
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    globals()[name] = module
    return module


def _namespace_module_name(name: str, profile: abi.ABIProfile) -> str:
    if profile is abi.NATIVE:
        return f"{__name__}.{name}"
    return profile.module_name(name)


def _load_namespace(
    name: str,
    version: str,
    *,
    profile: abi.ABIProfile = abi.NATIVE,
    _module_name_override: str | None = None,
) -> Namespace:
    module_name = (
        _module_name_override
        if _module_name_override is not None
        else _namespace_module_name(name, profile)
    )
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cast("Namespace", cached)

    namespace = Namespace(name, version, profile=profile)
    cast("Any", sys.modules)[module_name] = namespace
    if profile is abi.NATIVE:
        globals()[name] = namespace
    try:
        load_overlay_module_for(namespace)
    except BaseException:
        # Roll back so a retry can re-attempt overlay load.
        sys.modules.pop(module_name, None)
        if profile is abi.NATIVE:
            globals().pop(name, None)
        raise
    return namespace


def _class_from_namespace_profile(
    context: object, namespace_name: str, type_name: str
) -> object:
    if getattr(context, "__name__", None) == namespace_name:
        return getattr(context, type_name)
    profile = getattr(context, "_profile", None)
    if profile is None:
        gimeta = getattr(type(context), "gimeta", None)
        profile = getattr(gimeta, "profile", abi.NATIVE)
    version = defaults.resolve_version(namespace_name)
    assert version is not None
    namespace = _load_namespace(
        namespace_name, version, profile=cast("abi.ABIProfile", profile)
    )
    return getattr(namespace, type_name)


def _load_namespace_for_c(namespace_name: str) -> object:
    resolved = defaults.resolve_namespace_name(namespace_name)
    if resolved is None:
        raise AttributeError(namespace_name)
    namespace, version = resolved
    return _load_namespace(namespace, version)


from ginext import private as _private_hooks
_private_hooks.register_hook("class_from_namespace_profile", _class_from_namespace_profile)
_private_hooks.register_hook("load_namespace", _load_namespace_for_c)


def __getattr__(name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    if name in _LOCAL_MODULES:
        return _load_local_module(name)
    resolved = defaults.resolve_namespace_name(name)
    if resolved is None:
        raise AttributeError(f"GI namespace {name!r} is not available")

    namespace, version = resolved
    return _load_namespace(namespace, version)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(defaults.available_names()))


# GIRepository is a small, fundamental namespace used internally by ginext
# itself. Loading it eagerly puts it in sys.modules so that
# ``from ginext.GIRepository import EnumInfo`` works without a custom
# import hook. Pin 3.0 (the typelib of glib's bundled libgirepository-2.0 that
# ginext links): version resolution is ambiguous on Windows, where the legacy
# standalone gobject-introspection GIRepository-2.0 typelib coexists.
_load_namespace("GIRepository", "3.0")


__all__ = [
    "Signal",
    "SignalConnection",
    "UnownedSignalHandlerWarning",
    "PyGIDeprecationWarning",
    "PyGIWarning",
    "static_owner",
]
