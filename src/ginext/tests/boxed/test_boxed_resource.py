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

"""Boxed-type roundtrip tests.

Covers the wrapping path for GIR `<record>` types that have a registered
GType (boxed): ginext builds a real subclass of the internal GBoxedBase
plumbing instead of a stub, marshals the C boxed pointer in/out, and
exposes both static and instance methods.

Driver: `Gio.Resource` round-tripped through a tiny test fixture
gresource bundled in tests/fixtures/. The resource is loaded → the
returned wrapper is a `Gio.Resource` (not a stub) → its `_register()`
instance method runs → `Gio.resources_lookup_data` finds the bundled
bytes.
"""

from __future__ import annotations

import pathlib
from typing import Any

import pytest


_FIXTURES = pathlib.Path(__file__).parent / "fixtures"
_GRESOURCE = _FIXTURES / "test.gresource"


@pytest.fixture
def Gio() -> Any:
    from ginext import Gio as _Gio

    return _Gio


def test_resource_class_is_real_python_class(Gio: Any) -> None:
    """Gio.Resource is a heap-built class subclassing ginext's RecordBase.
    The `gimeta` attribute and `RecordBase` in the MRO prove the class
    came from the boxed-class builder."""
    resource_cls: Any = Gio.Resource
    assert isinstance(resource_cls, type)
    assert hasattr(resource_cls, "gimeta")
    # Static class methods land in tp_dict at build time.
    assert callable(Gio.Resource.load)


def test_resource_load_returns_wrapped_instance(Gio: Any) -> None:
    """`Resource.load(path)` produces a real boxed wrapper. The wrapper
    retains the underlying pointer so follow-on methods can dispatch
    correctly."""
    r = Gio.Resource.load(str(_GRESOURCE))
    assert isinstance(r, Gio.Resource)
    assert "Resource" in repr(r)


def test_resource_register_and_lookup_roundtrip(Gio: Any) -> None:
    """Pinning the entire path: load → _register → lookup_data. If any
    step regresses (return-marshal stops wrapping, self-bind stops
    accepting boxed wrappers, etc.), this test goes red."""
    r = Gio.Resource.load(str(_GRESOURCE))
    r._register()
    try:
        data = Gio.resources_lookup_data("/goi/test/hello.txt", 0)
    finally:
        r._unregister()
    assert data.get_data().startswith(b"hello, goi")


def test_resource_lookup_missing_path_raises(Gio: Any) -> None:
    """Negative case: looking up a path the resource doesn't carry must
    surface as a Python exception (not a crash). Confirms GError flow
    on a boxed-method call."""
    r = Gio.Resource.load(str(_GRESOURCE))
    r._register()
    try:
        with pytest.raises(Exception):
            Gio.resources_lookup_data("/no/such/path", 0)
    finally:
        r._unregister()


def test_resource_passed_back_as_argument(Gio: Any) -> None:
    """`Gio.resources_register` takes a Resource by pointer. The bind
    layer must unwrap our GBoxedBase wrapper to the raw boxed pointer
    and not e.g. pass the Python object's address."""
    r = Gio.Resource.load(str(_GRESOURCE))
    Gio.resources_register(r)
    try:
        data = Gio.resources_lookup_data("/goi/test/hello.txt", 0)
        assert data.get_data().startswith(b"hello, goi")
    finally:
        Gio.resources_unregister(r)
