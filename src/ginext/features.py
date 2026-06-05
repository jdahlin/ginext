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

"""Runtime feature flags for compatibility and migration work.

Feature flags are process-local. Umbrella flags, such as
``pygobject_compat``, set child defaults unless a child was explicitly
configured.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


PYGOBJECT_COMPAT = "pygobject_compat"
NEW_PROPERTY_API = "new_property_api"
NEW_SIGNAL_API = "new_signal_api"
GOBJECT_PROPERTY_CONSTRUCTOR = "gobject_property_constructor"
OLD_SIGNAL_API = "old_signal_api"
GERROR_BUILTIN_EXCEPTIONS = "gerror_builtin_exceptions"


_BUILTIN_DEFAULTS: dict[str, bool] = {
    PYGOBJECT_COMPAT: False,
    NEW_PROPERTY_API: True,
    NEW_SIGNAL_API: True,
    GOBJECT_PROPERTY_CONSTRUCTOR: True,
    OLD_SIGNAL_API: False,
    GERROR_BUILTIN_EXCEPTIONS: True,
}

_IMPLIED_DEFAULTS: dict[str, dict[str, bool]] = {
    PYGOBJECT_COMPAT: {
        NEW_PROPERTY_API: True,
        NEW_SIGNAL_API: True,
        GOBJECT_PROPERTY_CONSTRUCTOR: True,
        OLD_SIGNAL_API: True,
        GERROR_BUILTIN_EXCEPTIONS: False,
    },
}

_programmatic_overrides: dict[str, bool] = {}


def known_features() -> tuple[str, ...]:
    return tuple(_BUILTIN_DEFAULTS)


def is_enabled(name: str) -> bool:
    return snapshot()[_normalize_name(name)]


def set_enabled(name: str, enabled: bool) -> None:
    _programmatic_overrides[_normalize_name(name)] = bool(enabled)


def configure(mapping: Mapping[str, bool | int | str | None]) -> None:
    for name, enabled in mapping.items():
        set_enabled(name, _coerce_bool(enabled, name))


def reset_for_test() -> None:
    _programmatic_overrides.clear()


def overrides_snapshot() -> dict[str, bool]:
    """Return a copy of the current programmatic overrides (test isolation seam)."""
    return dict(_programmatic_overrides)


def overrides_restore(snapshot: dict[str, bool]) -> None:
    """Restore programmatic overrides from :func:`overrides_snapshot` (test seam).

    Tests toggle process-global feature flags via :func:`set_enabled`; restoring
    a flag with ``set_enabled(name, False)`` writes an explicit override that
    outranks implied defaults, so a leaked override silently changes behaviour
    for unrelated tests. Snapshot/restore around each test keeps toggles local.
    """
    _programmatic_overrides.clear()
    _programmatic_overrides.update(snapshot)


def snapshot() -> dict[str, bool]:
    explicit = _env_features()
    explicit.update(_programmatic_overrides)

    result = dict(_BUILTIN_DEFAULTS)
    result.update(explicit)

    for umbrella, implied in _IMPLIED_DEFAULTS.items():
        if result[umbrella]:
            for name, enabled in implied.items():
                if name not in explicit:
                    result[name] = enabled

    return result


def _env_features() -> dict[str, bool]:
    result: dict[str, bool] = {}
    raw = os.environ.get("GINEXT_FEATURES")
    if raw:
        for entry in raw.split(","):
            entry = entry.strip()
            if not entry:
                continue
            name, enabled = _parse_entry(entry)
            result[name] = enabled
    raw_gerror_builtin = os.environ.get("GINEXT_GERROR_BUILTIN_EXCEPTIONS")
    if raw_gerror_builtin is not None:
        result[GERROR_BUILTIN_EXCEPTIONS] = _coerce_bool(
            raw_gerror_builtin, GERROR_BUILTIN_EXCEPTIONS
        )
    return result


def _parse_entry(entry: str) -> tuple[str, bool]:
    if "=" in entry:
        name, _, raw_value = entry.partition("=")
        name = _normalize_name(name.strip())
        return name, _coerce_bool(raw_value.strip(), name)
    if entry.startswith("+"):
        return _normalize_name(entry[1:].strip()), True
    if entry.startswith("-"):
        return _normalize_name(entry[1:].strip()), False
    if entry.startswith("no-"):
        return _normalize_name(entry[3:].strip()), False
    return _normalize_name(entry), True


def _coerce_bool(value: bool | int | str | None, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise ValueError(f"malformed GINEXT_FEATURES value for {name!r}: {value!r}")
    if value is None:
        return False
    text = value.strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    raise ValueError(f"malformed GINEXT_FEATURES value for {name!r}: {value!r}")


def _normalize_name(name: str) -> str:
    normalized = name.replace("-", "_")
    if normalized not in _BUILTIN_DEFAULTS:
        raise KeyError(f"unknown ginext feature flag {name!r}")
    return normalized
