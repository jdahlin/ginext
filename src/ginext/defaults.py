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

import ast
import os
from importlib import metadata
from pathlib import Path
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


# Implied co-required versions (e.g. Gtk 4.0 implies Gdk 4.0) are namespace-
# ecosystem policy, not core's: each overlay package declares its own via the
# "ginext.implied_defaults" entry-point group (value is a dict, or a callable
# returning one, keyed by (namespace, version)). Discovered lazily and cached.
_implied_defaults_map_cache: dict[tuple[str, str], dict[str, str]] | None = None


def _discover_implied_defaults() -> dict[tuple[str, str], dict[str, str]]:
    registry: dict[tuple[str, str], dict[str, str]] = {}
    for entry in metadata.entry_points(group="ginext.implied_defaults"):
        try:
            data = entry.load()
        except ImportError, AttributeError:
            continue
        if callable(data):
            data = data()
        for key, mapping in dict(data).items():
            registry.setdefault((key[0], key[1]), {}).update(mapping)
    return registry


def implied_defaults_map() -> dict[tuple[str, str], dict[str, str]]:
    global _implied_defaults_map_cache
    if _implied_defaults_map_cache is None:
        _implied_defaults_map_cache = _discover_implied_defaults()
    return _implied_defaults_map_cache


# These caches memoize pure functions of their inputs (environment + installed
# typelibs), so they are keyed on those inputs and re-derive automatically when
# the inputs change. That keeps them semantically transparent: behaviour is
# identical whether the cache is cold, warm, or repopulated — no explicit
# invalidation is needed (and changing GINEXT_VERSIONS/GINEXT_APP/GI_TYPELIB_PATH
# mid-process, as tests do, is reflected immediately).
_installed_cache: dict[str, list[str]] | None = None
_installed_cache_key: str | None = None
_project_defaults_cache: dict[str, str] | None = None
_project_defaults_cache_key: str | None = None
# The require() registry is imperative session state (not an input-derived
# cache); it is the one piece of mutable resolution state. Tests isolate it via
# the autouse fixture in src/ginext/tests/conftest.py.
_required_versions_cache: dict[str, str] | None = None


def _installed_versions() -> dict[str, list[str]]:
    global _installed_cache, _installed_cache_key
    key = os.environ.get("GI_TYPELIB_PATH", "")
    if _installed_cache is None or _installed_cache_key != key:
        from . import private

        _installed_cache = private.installed_versions()
        _installed_cache_key = key
    assert _installed_cache is not None
    return _installed_cache


def _env_versions() -> dict[str, str]:
    raw = os.environ.get("GINEXT_VERSIONS")
    if not raw:
        return {}
    result: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError(f"malformed GINEXT_VERSIONS entry {entry!r}")
        namespace, _, version = entry.partition(":")
        namespace = namespace.strip()
        version = version.strip()
        if not namespace or not version:
            raise ValueError(f"malformed GINEXT_VERSIONS entry {entry!r}")
        result[namespace] = version
    return result


def required_versions() -> dict[str, str]:
    global _required_versions_cache
    if _required_versions_cache is None:
        _required_versions_cache = {}
    return _required_versions_cache


def require(namespace: str, version: str) -> None:
    if not isinstance(namespace, str) or not namespace:
        raise ValueError(f"Namespace must be a non-empty string, not {namespace!r}")
    if not isinstance(version, str):
        raise ValueError(f"Namespace version needs to be a string, not {version!r}")

    existing = required_versions().get(namespace)
    if existing is not None and existing != version:
        raise ValueError(
            f"Namespace {namespace} already requires version {existing}, cannot require {version}"
        )
    required_versions()[namespace] = version


def _literal_default_versions(source: str, filename: str) -> dict[str, str]:
    module = ast.parse(source, filename=filename)
    result: dict[str, str] | None = None
    for node in module.body:
        if not isinstance(node, ast.Assign):
            raise ValueError(f"{filename}: only DEFAULT_VERSIONS assignment is allowed")
        if not all(
            isinstance(target, ast.Name) and target.id == "DEFAULT_VERSIONS"
            for target in node.targets
        ):
            raise ValueError(f"{filename}: only DEFAULT_VERSIONS assignment is allowed")
        if result is not None:
            raise ValueError(f"{filename}: duplicate DEFAULT_VERSIONS assignment")
        value = ast.literal_eval(node.value)
        if not isinstance(value, dict):
            raise TypeError(f"{filename}: DEFAULT_VERSIONS must be a dict")
        result = {}
        for key, version in value.items():
            if not isinstance(key, str) or not isinstance(version, str):
                raise TypeError(f"{filename}: DEFAULT_VERSIONS must map str to str")
            result[key] = version
    return result or {}


def load_gidefaults_file(path: os.PathLike[str] | str) -> dict[str, str]:
    with Path(path).open(encoding="utf-8") as f:
        return _literal_default_versions(f.read(), str(path))


def _main_package_for_test() -> str | None:
    import __main__

    spec = __main__.__spec__
    if spec is None:
        return None
    main_name = spec.name
    if not main_name:
        return None
    return main_name.split(".", 1)[0]


def _packages_distributions_for_test() -> Mapping[str, list[str]]:
    return metadata.packages_distributions()


def _distribution_name_from_main() -> str | None:
    top_level = _main_package_for_test()
    if not top_level:
        return None
    distributions = _packages_distributions_for_test().get(top_level, [])
    if len(distributions) > 1:
        raise RuntimeError(
            f"cannot infer ginext app distribution for {top_level!r}: "
            f"{', '.join(distributions)}"
        )
    if len(distributions) == 1:
        return distributions[0]
    return None


def _load_project_defaults_uncached() -> dict[str, str] | None:
    explicit = os.environ.get("GINEXT_APP")
    app = explicit or _distribution_name_from_main()
    if not app:
        return None
    try:
        dist = metadata.distribution(app)
    except metadata.PackageNotFoundError as exc:
        if explicit:
            raise LookupError(f"ginext app distribution {app!r} was not found") from exc
        return None
    source = dist.read_text("gidefaults.py")
    if source is None:
        return {}
    return _literal_default_versions(source, f"{app}.dist-info/gidefaults.py")


def _load_app_defaults_uncached_for_test() -> dict[str, str] | None:
    return _load_project_defaults_uncached()


def _app_cache_key() -> str:
    # The app defaults derive from GINEXT_APP (or, when unset, the app inferred
    # from __main__, which is fixed for the process). Keying on GINEXT_APP makes
    # the cache re-derive when that env var changes.
    return os.environ.get("GINEXT_APP", "")


def load_app_defaults() -> dict[str, str] | None:
    global _project_defaults_cache, _project_defaults_cache_key
    key = _app_cache_key()
    if _project_defaults_cache is None or _project_defaults_cache_key != key:
        loaded = _load_app_defaults_uncached_for_test()
        _project_defaults_cache = dict(loaded or {})
        _project_defaults_cache_key = key
    return _project_defaults_cache


def set_app_defaults_for_test(mapping: dict[str, str] | None) -> None:
    global _project_defaults_cache, _project_defaults_cache_key
    _project_defaults_cache = dict(mapping or {})
    _project_defaults_cache_key = _app_cache_key()


def list_installed_versions_for_test(namespace: str) -> list[str]:
    return list(_installed_versions().get(namespace, []))


def project_defaults() -> dict[str, str]:
    return dict(load_app_defaults() or {})


def _implied_defaults(defaults: dict[str, str]) -> dict[str, str]:
    implied: dict[str, str] = {}
    for namespace, version in defaults.items():
        implied.update(implied_defaults_map().get((namespace, version), {}))
    return implied


def resolve_version(namespace: str) -> str | None:
    required = required_versions()
    if namespace in required:
        return required[namespace]

    env = _env_versions()
    if namespace in env:
        return env[namespace]

    project = project_defaults()
    if namespace in project:
        return project[namespace]

    direct = dict(project)
    direct.update(env)
    implied = _implied_defaults(direct)
    if namespace in implied:
        return implied[namespace]

    installed = _installed_versions().get(namespace)
    if installed:
        return installed[0]
    raise LookupError(f"GI namespace {namespace!r} is not available")


_FULL_SUFFIX_RE = re.compile(
    r"^(?P<namespace>[A-Za-z][A-Za-z0-9]*)_(?P<version>[0-9]+(?:_[0-9]+)*)$"
)


def split_suffix(name: str) -> tuple[str, str] | None:
    full = _FULL_SUFFIX_RE.match(name)
    if full is not None:
        return (
            full.group("namespace"),
            full.group("version").replace("_", "."),
        )

    for i in range(len(name) - 1, 0, -1):
        if not name[i].isdigit():
            base = name[: i + 1]
            digits = name[i + 1 :]
            if not digits or not base[-1].isalpha():
                return None
            for version in _installed_versions().get(base, []):
                if version.split(".", 1)[0] == digits:
                    return base, version
            return None
    return None


def resolve_namespace_name(name: str) -> tuple[str, str] | None:
    suffixed = split_suffix(name)
    if suffixed is not None:
        return suffixed

    try:
        version = resolve_version(name)
    except LookupError:
        return None
    if version is None:
        return None
    return name, version


def available_names() -> set[str]:
    names = set(_installed_versions())
    names.update(_env_versions())
    project = project_defaults()
    names.update(project)
    names.update(_implied_defaults(project))
    return names


# NOTE: there is deliberately no reset_caches(). Built namespace, class, enum and
# boxed objects are process-global singletons whose identity must stay stable —
# code (and the pygobject-compat layer) holds references to them, so tearing them
# down and rebuilding would hand back fresh objects that fail `is`/`isinstance`
# checks against the originals. The resolution caches above are keyed on their
# inputs and re-derive on change, so nothing needs explicit invalidation. Tests
# that must observe a cold build run in a fresh subprocess (@pytest.mark.subprocess).
