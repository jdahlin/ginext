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

"""Descriptor-build smoke tests for return-type shapes that the
inventory sweep previously rejected.

These callables don't have easy invocation harnesses inside the
typelibs we ship, so each test only verifies that
build_callable_descriptor no longer raises
NotImplementedError. The runtime marshaling for these shapes is
exercised separately when a typelib is available.
"""

from __future__ import annotations

import pytest

from ginext import private


_LOOKUP_ERRORS = (AttributeError, ImportError, RuntimeError)


def _find_method(namespace: str, version: str, qualified: str) -> tuple[object, bool]:
    """Resolve a qualified name to (info, has_self) or skip if the
    namespace/method isn't installed on this host."""
    try:
        private.require_namespace(namespace, version)
    except _LOOKUP_ERRORS as exc:
        pytest.skip(f"{namespace}/{version} unavailable: {exc}")
    parts = qualified.split(".")
    if parts[0] != namespace:
        pytest.fail(f"{qualified!r} does not start with {namespace!r}")
    if len(parts) == 2:
        try:
            kind, info = private.namespace_find(namespace, version, parts[1])
        except _LOOKUP_ERRORS as exc:
            pytest.skip(f"{qualified}: {exc}")
        if kind != "function":
            pytest.skip(f"{qualified}: kind={kind!r}")
        return info, False
    container, method = parts[1], parts[2]
    try:
        kind, info = private.namespace_find(namespace, version, container)
    except _LOOKUP_ERRORS as exc:
        pytest.skip(f"{namespace}.{container} not found: {exc}")
    if kind == "object":
        methods = info.object_info()["methods"]
    elif kind in ("record", "union"):
        methods = info.record_info()["methods"]
    else:
        pytest.skip(f"{namespace}.{container}: kind={kind!r}")
    for m in methods:
        if m.get_name().replace("-", "_") == method:
            return m, m.is_method()
    pytest.skip(f"{qualified}: method not found")


def test_gslist_of_error_return_descriptor_builds() -> None:
    """Gda.DataModelDir.get_errors returns GSList<GError*>."""
    info, has_self = _find_method("Gda", "5.0", "Gda.DataModelDir.get_errors")
    private.build_callable_descriptor(info, "Gda.DataModelDir.get_errors", has_self)


def test_opaque_hash_void_value_return_descriptor_builds() -> None:
    """Grl.range_value_hashtable_new returns GHashTable<gpointer, RangeValue>."""
    info, has_self = _find_method("Grl", "0.3", "Grl.range_value_hashtable_new")
    private.build_callable_descriptor(info, "Grl.range_value_hashtable_new", has_self)


def test_opaque_hash_void_key_return_descriptor_builds() -> None:
    """Grl.g_value_hashtable_new_direct returns GHashTable<gpointer, GValue>."""
    info, has_self = _find_method("Grl", "0.3", "Grl.g_value_hashtable_new_direct")
    private.build_callable_descriptor(
        info, "Grl.g_value_hashtable_new_direct", has_self
    )
