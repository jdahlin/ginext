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

import importlib
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, cast

from .registrar import OverlayRegistrar

if TYPE_CHECKING:
    import types as _types
    from ginext.namespace import Namespace


_loaded_overlay_namespaces: set[tuple[str, str]] = set()
_loaded_overlay_modules: dict[str, object] = {}
_MISSING = object()
_OVERLAY_ENTRY_POINTS: dict[str, tuple[str, str]] | None = None


def reset_for_test() -> None:
    _loaded_overlay_namespaces.clear()
    _loaded_overlay_modules.clear()


def _overlay_entry_points() -> dict[str, tuple[str, str]]:
    global _OVERLAY_ENTRY_POINTS
    if _OVERLAY_ENTRY_POINTS is None:
        _OVERLAY_ENTRY_POINTS = {}
        for ep in importlib.metadata.entry_points(group="ginext.overlays"):
            # Values are spec-valid dotted object references (e.g.
            # "ginext_gtk:_overlays.Gtk") so Python 3.15's importlib.metadata,
            # which validates entry points eagerly, accepts them. Map the dotted
            # tail back to the overlay file path.
            pkg, rel = ep.value.split(":", 1)
            rel = rel.replace(".", "/") + ".py"
            _OVERLAY_ENTRY_POINTS[ep.name] = (pkg, rel)
    return _OVERLAY_ENTRY_POINTS


def _load_overlay_module_from_path(
    overlay_module: str, overlay_path: Path
) -> _types.ModuleType | None:
    sys.modules.pop(overlay_module, None)
    spec = importlib.util.spec_from_file_location(overlay_module, overlay_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[overlay_module] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(overlay_module, None)
        raise
    return module


def _load_overlay_module_from_entry_point(
    overlay_module: str, ns_name: str
) -> "_types.ModuleType | None":
    paths = _overlay_entry_points()
    if ns_name not in paths:
        return None
    pkg, rel = paths[ns_name]
    try:
        pkg_mod = importlib.import_module(pkg)
    except ModuleNotFoundError:
        return None
    pkg_file = getattr(pkg_mod, "__file__", None)
    if pkg_file is None:
        return None
    overlay_path = Path(pkg_file).parent / rel
    if not overlay_path.exists():
        return None
    return _load_overlay_module_from_path(overlay_module, overlay_path)


def _load_overlay_module_from_env_path(
    overlay_module: str, ns_name: str
) -> "_types.ModuleType | None":
    overlay_path_env = os.environ.get("GINEXT_OVERLAY_PATH")
    if not overlay_path_env:
        return None
    for base in overlay_path_env.split(os.pathsep):
        if not base:
            continue
        overlay_path = Path(base) / f"{ns_name}.py"
        if overlay_path.exists():
            return _load_overlay_module_from_path(overlay_module, overlay_path)
    return None


def _load_overlay_module_from_package_file(
    overlay_module: str, ns_name: str
) -> "_types.ModuleType | None":
    ginext = sys.modules["ginext"]
    package_file = getattr(ginext, "__file__", None)
    if package_file is None:
        return None
    package_dir = Path(package_file).parent
    package_path = getattr(ginext, "__path__", None)
    if package_path is not None and str(package_dir) not in package_path:
        try:
            package_path.insert(0, str(package_dir))
        except AttributeError:
            package_path.append(str(package_dir))
    overlay_path = package_dir / "_overlays" / f"{ns_name}.py"
    if not overlay_path.exists():
        return None
    return _load_overlay_module_from_path(overlay_module, overlay_path)


def load_overlay_module_for(namespace_module: Namespace) -> None:
    """Load ``ginext._overlays.<ns_name>`` if present, with a registrar
    temporarily attached as ``<namespace_module>.overlay``. Idempotent."""
    ns_name = namespace_module.__name__
    profile_name = namespace_module._profile.name
    key = (profile_name, ns_name)
    if key in _loaded_overlay_namespaces:
        return
    _loaded_overlay_namespaces.add(key)

    try:
        ginext = sys.modules["ginext"]
        overlay_module = f"ginext._overlays.{ns_name}"
        previous_attr = vars(ginext).get(ns_name, _MISSING)
        previous_module = sys.modules.get(f"ginext.{ns_name}", _MISSING)
        setattr(ginext, ns_name, namespace_module)
        _module: Any = namespace_module
        sys.modules[f"ginext.{ns_name}"] = _module
        _module.overlay = OverlayRegistrar(namespace_module)
        try:
            module = _loaded_overlay_modules.get(ns_name)
            if module is None:
                module = _load_overlay_module_from_env_path(overlay_module, ns_name)
                if module is None:
                    module = _load_overlay_module_from_entry_point(
                        overlay_module, ns_name
                    )
                if module is None:
                    try:
                        module = importlib.import_module(overlay_module)
                    except ModuleNotFoundError as exc:
                        # Re-raise unless it's the overlay file itself that's missing —
                        # a missing dep inside the overlay shouldn't be silently swallowed.
                        if exc.name != overlay_module:
                            raise
                        module = _load_overlay_module_from_package_file(
                            overlay_module, ns_name
                        )
                if module is not None:
                    _loaded_overlay_modules[ns_name] = module
        finally:
            try:
                delattr(namespace_module, "overlay")
            except AttributeError:
                pass
            if previous_attr is _MISSING:
                try:
                    delattr(ginext, ns_name)
                except AttributeError:
                    pass
            else:
                setattr(ginext, ns_name, previous_attr)
            if previous_module is _MISSING:
                sys.modules.pop(f"ginext.{ns_name}", None)
            else:
                sys.modules[f"ginext.{ns_name}"] = cast("Any", previous_module)
        if module is not None:
            apply = getattr(module, "apply_to_namespace", None)
            if apply is not None:
                apply(namespace_module)
    except Exception:
        _loaded_overlay_namespaces.discard(key)
        raise
