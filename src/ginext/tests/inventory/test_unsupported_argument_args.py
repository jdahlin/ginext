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

"""Backlog tests for every callable currently rejected by ginext's
invoke layer with reason "unsupported argument type is outside the
current ginext invoke slice".

The list is captured in ``_unsupported_argument_args.json``, regenerated
from a fresh ``inventory_sweep.py`` run via
``scripts/inventory_snapshot_arg_args.py``. Each test calls
``build_callable_descriptor`` directly so it FAILS today with
``NotImplementedError`` and PASSES once ginext can marshal the
callable's unsupported in-argument shape. Tests skip when their typelib
is not installed on the host.

Version-conflict caveat
~~~~~~~~~~~~~~~~~~~~~~~
libgirepository disallows loading two major versions of the same
namespace into one process (real apps pick Gtk 3 *or* Gtk 4 once and
stick with it). When the snapshot covers callables in both Gtk-3.0 and
Gtk-4.0 — same for Clutter, Cogl, GtkSource, etc. — whichever version
``require_namespace`` happens to bind first wins, and every later test
for the other version reports skipped with reason "version conflict".
To exercise both, run the test in two passes with ``-k Gtk-3`` / ``-k
Gtk-4`` (or pin a chosen version via deselect markers).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest

from ginext import private


_SNAPSHOT_PATH = Path(__file__).with_name("_unsupported_argument_args.json")
_NAMESPACE_LOAD_ERRORS = (AttributeError, ImportError, RuntimeError)


def _load_snapshot() -> list[dict[str, Any]]:
    if not _SNAPSHOT_PATH.exists():
        return []
    return cast("list[dict[str, Any]]", json.loads(_SNAPSHOT_PATH.read_text()))


def _snapshot_param(entry: dict[str, Any]) -> Any:
    marks: tuple[Any, ...] = ()
    if entry.get("skip_reason"):
        marks = (pytest.mark.xfail(reason=entry["skip_reason"], strict=False),)
    return pytest.param(
        entry["namespace"],
        entry["version"],
        entry["qualified"],
        entry["kind"],
        marks=marks,
        id=entry["qualified"],
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "qualified" not in metafunc.fixturenames:
        return
    entries = [entry for entry in _load_snapshot() if not entry.get("is_gtk3")]
    if not entries:
        metafunc.parametrize(
            "namespace,version,qualified,kind",
            [
                pytest.param(
                    "",
                    "",
                    "",
                    "",
                    marks=pytest.mark.skip(
                        reason=f"snapshot {_SNAPSHOT_PATH.name} not generated; "
                        f"run scripts/inventory_snapshot_arg_args.py"
                    ),
                )
            ],
        )
        return
    metafunc.parametrize(
        "namespace,version,qualified,kind",
        [_snapshot_param(e) for e in entries],
    )


@pytest.fixture(scope="session")
def loaded_namespaces() -> Callable[[str, str], BaseException | None]:
    """Load namespaces lazily, memoizing the first attempt's outcome.

    Returns a callable that takes (namespace, version) and either returns
    None on success or the exception raised by ``require_namespace`` on
    failure. Loads are deferred so a per-typelib failure in one library
    cannot fail-cascade by changing the global load order.
    """
    cache: dict[tuple[str, str], BaseException | None] = {}

    def get(namespace: str, version: str) -> BaseException | None:
        key = (namespace, version)
        if key not in cache:
            try:
                private.require_namespace(*key)
                cache[key] = None
            except _NAMESPACE_LOAD_ERRORS as exc:
                cache[key] = exc
        return cache[key]

    return get


@pytest.fixture
def callable_info(
    namespace: str,
    version: str,
    qualified: str,
    loaded_namespaces: Callable[[str, str], BaseException | None],
) -> tuple[object, bool]:
    """Resolve a qualified name in the snapshot to a (callable_info,
    has_self) pair, skipping cleanly if the typelib or container is
    unavailable."""
    load_error = loaded_namespaces(namespace, version)
    if load_error is not None:
        message = str(load_error)
        if "is already loaded" in message:
            pytest.skip(
                f"{namespace}/{version} version conflict: another version is "
                f"already loaded in this process ({load_error})"
            )
        pytest.skip(f"{namespace}/{version} unavailable: {load_error}")

    parts = qualified.split(".")
    if parts[0] != namespace:
        raise AssertionError(
            f"qualified name {qualified!r} does not start with namespace {namespace!r}"
        )

    if len(parts) == 2:
        kind, info = private.namespace_find(namespace, version, parts[1])
        if kind != "function":
            pytest.skip(f"{qualified}: namespace_find returned kind={kind!r}")
        return info, False

    if len(parts) == 3:
        container, method = parts[1], parts[2]
        try:
            kind, info = private.namespace_find(namespace, version, container)
        except _NAMESPACE_LOAD_ERRORS as exc:
            pytest.skip(f"{namespace}.{container} not found: {exc}")
        if kind == "object":
            methods = info.object_info()["methods"]
        elif kind in ("record", "union"):
            methods = info.record_info()["methods"]
        else:
            pytest.skip(f"{namespace}.{container} is kind={kind!r}, no methods")
        for method_info in methods:
            if method_info.get_name().replace("-", "_") == method:
                return method_info, method_info.is_method()
        pytest.skip(f"{qualified} not found among {len(methods)} methods")

    pytest.skip(f"unexpected qualified-name shape: {qualified!r}")


def test_argument_arg_descriptor_builds(
    qualified: str,
    callable_info: tuple[object, bool],
    kind: str,
) -> None:
    info, has_self = callable_info
    private.build_callable_descriptor(info, qualified, has_self)
