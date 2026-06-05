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

from typing import Any
import pytest

from ginext import private


_DESCRIPTOR_BUILD_ERRORS = (AttributeError, RuntimeError, TypeError, ValueError)


CORE_NAMESPACES = [
    pytest.param("GLib", id="GLib"),
    pytest.param("GObject", id="GObject"),
    pytest.param("Gio", id="Gio"),
]


CORE_OBJECT_NAMESPACES = [
    pytest.param("GObject", id="GObject"),
    pytest.param("Gio", id="Gio"),
]


def _namespace_version(name: str) -> str:
    import ginext

    return ".".join(str(c) for c in getattr(ginext, name).__version__)


def _namespace_infos(name: str) -> list[tuple[str, str, Any]]:
    version = _namespace_version(name)
    infos: list[tuple[str, str, Any]] = []
    for member_name in private.namespace_dir(name, version):
        kind, info = private.namespace_find(name, version, member_name)
        infos.append((member_name, kind, info))
    return infos


@pytest.mark.parametrize("namespace", CORE_NAMESPACES)
def test_namespace_dir_entries_are_resolvable(namespace: str) -> None:
    infos = _namespace_infos(namespace)

    assert infos
    assert all(member_name for member_name, _kind, _info in infos)


@pytest.mark.parametrize("namespace", CORE_NAMESPACES)
def test_top_level_functions_build_or_reject_cleanly(namespace: str) -> None:
    functions = [
        (member_name, info)
        for member_name, kind, info in _namespace_infos(namespace)
        if kind == "function"
    ]

    assert functions
    built = 0
    rejected = 0
    unexpected: list[tuple[str, str, str]] = []

    for member_name, info in functions:
        py_name = info.get_name().replace("-", "_")
        try:
            private.build_callable_descriptor(info, f"{namespace}.{py_name}", False)
        except NotImplementedError:
            rejected += 1
        # pragma: no cover - failure formatting path
        except _DESCRIPTOR_BUILD_ERRORS as exc:
            unexpected.append((member_name, type(exc).__name__, str(exc)))
        else:
            built += 1

    assert built
    assert unexpected == []


@pytest.mark.parametrize("namespace", CORE_OBJECT_NAMESPACES)
def test_object_methods_build_or_reject_cleanly(namespace: str) -> None:
    object_methods: list[tuple[str, Any]] = []
    for class_name, kind, info in _namespace_infos(namespace):
        if kind != "object":
            continue
        data = info.object_info()
        object_methods.extend(
            (class_name, method_info)
            for method_info in data["methods"]
            if method_info.get_name().replace("-", "_") != "new"
        )

    assert object_methods
    built = 0
    rejected = 0
    unexpected: list[tuple[str, str, str, str]] = []

    for class_name, method_info in object_methods:
        method_name = method_info.get_name().replace("-", "_")
        has_self = method_info.is_method()
        try:
            private.build_callable_descriptor(
                method_info,
                f"{namespace}.{class_name}.{method_name}",
                has_self,
            )
        except NotImplementedError:
            rejected += 1
        # pragma: no cover - failure formatting path
        except _DESCRIPTOR_BUILD_ERRORS as exc:
            unexpected.append((class_name, method_name, type(exc).__name__, str(exc)))
        else:
            built += 1

    assert built
    assert unexpected == []
