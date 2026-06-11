# Copyright 2026 Johan Dahlin
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
from typing import Any

import ginext
from ginext import features
from ginext import PyGIDeprecationWarning
from ginext import PyGIWarning


if not features.is_enabled(features.PYGOBJECT_COMPAT):
    raise ModuleNotFoundError("No module named 'gi'")

from . import _gtype_compat as _gtype_compat  # noqa: F401 — patches GTypeMeta at load time
from . import importer as importer


__version__ = "3.52.0"
version_info = (3, 52, 0)


def check_version(version: str | tuple[int, ...]) -> None:
    if isinstance(version, str):
        parts = tuple(int(part) for part in version.split("."))
    else:
        parts = tuple(version)
    if parts > version_info:
        raise ValueError(
            f"pygobject version {version!r} is required, found {__version__}"
        )


def require_version(namespace: str, version: str) -> None:
    ginext.defaults.require(namespace, version)


def require_versions(versions: dict[str, str]) -> None:
    for namespace, version in versions.items():
        require_version(namespace, version)


def require_foreign(namespace: str, symbol: str | None = None) -> None:
    module = importlib.import_module(namespace)
    if symbol is not None and not hasattr(module, symbol):
        raise ImportError(f"cannot import name {symbol!r} from foreign namespace")
    if namespace == "cairo":
        ginext.private.require_namespace("cairo", "1.0")
        ginext.private.ensure_cairo_gobject_types()


def __getattr__(name: str) -> Any:
    if name in {
        "repository",
        "module",
        "_gi",
        "_ossighelper",
        "_propertyhelper",
        "_signalhelper",
        "docstring",
        "events",
        "importer",
        "overrides",
        "types",
    }:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(name)


__all__ = [
    "PyGIDeprecationWarning",
    "PyGIWarning",
    "__version__",
    "check_version",
    "require_foreign",
    "require_version",
    "require_versions",
    "version_info",
]
