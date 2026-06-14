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

"""GObject *fundamental* (non-GObject) wrapper coverage.

Fundamentals derive from GTypeInstance directly rather than GObject,
so the usual g_object_ref / g_object_unref / qdata machinery is wrong
for them. Regress ships a few minimal fundamental types we can pin
behaviour against:

  TestFundamentalObject              abstract base, GTypeValueTable-driven
  TestFundamentalSubObject           concrete, has get_data/set_data
  TestFundamentalObjectNoGetSetFunc  concrete, public `data` field, no funcs
  TestFundamentalHiddenSubObject     anonymous subclass returned by a fn
  Bitmask                            primitive (int-shaped) fundamental

The shape of these tests is loosely modelled on PyGObject's
tests/test_fundamental.py, but rewritten to use pytest fixtures and
parametrisation rather than copying the suite verbatim. Cases that
don't work yet on goi are xfail(strict=False) so they flip green
automatically when the underlying support lands.
"""

from __future__ import annotations

import pytest

import gc
from collections.abc import Iterator

from ginext.namespace import Namespace
from .support import open_namespace_for_test


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _restore_gvalue_fallback() -> Iterator[None]:
    # Tests below install or clear the GValue->Python fallback, which is
    # process-global. Under xdist a worker that also runs the gst suite would
    # otherwise be left without gst's fallback and fail (NotImplementedError on a
    # GstFraction value). Snapshot and restore it around every test here.
    from ginext import private

    saved = private.gvalue_get_to_py_fallback()
    try:
        yield
    finally:
        private.gvalue_set_to_py_fallback(saved)


@pytest.fixture
def regress(call_mode: str) -> Namespace:
    return open_namespace_for_test(call_mode, "Regress", "1.0")


@pytest.fixture
def sub_obj(regress: Namespace) -> object:
    """A live TestFundamentalSubObject built via the .new() classmethod."""
    return regress.TestFundamentalSubObject.new("foo")


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_new_classmethod_returns_instance(regress: Namespace) -> None:
    obj = regress.TestFundamentalSubObject.new("foo")
    assert obj is not None


def test_no_get_set_func_new(regress: Namespace) -> None:
    obj = regress.TestFundamentalObjectNoGetSetFunc.new("bar")
    assert obj is not None


def test_create_hidden_subclass(regress: Namespace) -> None:
    """The C side returns a TestFundamentalHiddenSubObject; the Python
    wrapper reads as a TestFundamentalObject (the public super)."""
    obj = regress.test_create_fundamental_hidden_class_instance()
    assert obj is not None


def test_abstract_base_rejected(regress: Namespace) -> None:
    """TestFundamentalObject is marked abstract — direct construction
    should raise. (The current G_TYPE_IS_ABSTRACT check happens to work
    here because the type system tags fundamentals abstract too.)"""
    with pytest.raises(TypeError):
        regress.TestFundamentalObject()


def test_direct_construction_no_args_rejected(regress: Namespace) -> None:
    with pytest.raises(TypeError):
        regress.TestFundamentalSubObject()


# ---------------------------------------------------------------------------
# Argument round-trips
# ---------------------------------------------------------------------------


def test_argument_in_returns_true(regress: Namespace, sub_obj: object) -> None:
    assert regress.test_fundamental_argument_in(sub_obj) is True


def test_argument_out_returns_object(regress: Namespace, sub_obj: object) -> None:
    other = regress.test_fundamental_argument_out(sub_obj)
    assert other is not None


def test_array_of_fundamental_objects_in_nonempty(regress: Namespace) -> None:
    assert regress.test_array_of_fundamental_objects_in(
        [regress.TestFundamentalSubObject.new("a")]
    )


def test_array_of_fundamental_objects_in_empty(regress: Namespace) -> None:
    """Empty-array path — what test_regress.py covers today, kept here to
    centralise the fundamental-flavoured bits."""
    regress.test_array_of_fundamental_objects_in([])


def test_array_of_fundamental_objects_out(regress: Namespace) -> None:
    result = regress.test_array_of_fundamental_objects_out()
    assert len(list(result)) == 2


# ---------------------------------------------------------------------------
# Properties / attribute access
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("attr", ["data", "refcount"])
def test_attribute_access(sub_obj: object, attr: str) -> None:
    assert getattr(sub_obj, attr) is not None


def test_isinstance_inheritance(regress: Namespace, sub_obj: object) -> None:
    assert isinstance(sub_obj, regress.TestFundamentalObject)


def test_two_distinct_objects_unequal(regress: Namespace) -> None:
    a = regress.TestFundamentalSubObject.new("a")
    b = regress.TestFundamentalSubObject.new("b")
    assert a != b


# ---------------------------------------------------------------------------
# Lifetime
# ---------------------------------------------------------------------------


def test_construct_then_drop(regress: Namespace) -> None:
    """Hot loop equivalent of the xdist crash that exposed the missing
    fundamental detection. Each iteration creates a fundamental, lets
    it go out of scope, and forces a GC round."""
    for _ in range(10):
        obj = regress.TestFundamentalSubObject.new("data")
        del obj
        gc.collect()


# ---------------------------------------------------------------------------
# Primitive (int-shaped) fundamental — Regress.Bitmask
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="primitive int-shaped fundamental wrappers are not implemented yet",
    strict=False,
)
def test_primitive_fundamental_bitmask(regress: Namespace) -> None:
    bm = regress.Bitmask(2)
    assert getattr(bm, "v") == 2


# ---------------------------------------------------------------------------
# GValue fallback for custom-fundamental GTypes (pygi_gvalue_set_to_py_fallback)
# ---------------------------------------------------------------------------
# Regress.Bitmask is a self-fundamental, non-instantiatable, non-boxed GType
# that has a value table — the ideal vehicle to exercise the fallback path.


@pytest.fixture
def regress_bitmask_gtype(regress: Namespace) -> int:
    """Return the GType of Regress.Bitmask.

    Accessing ``regress.Bitmask`` triggers GLib type registration so
    ``GObject.type_from_name`` can find it — no ctypes needed.
    """
    import ginext

    _ = regress.Bitmask  # triggers type registration in the GLib type system
    gtype = ginext.GObject.type_from_name("RegressBitmask")
    assert gtype != 0, (
        "RegressBitmask GType not registered after accessing Bitmask class"
    )
    return int(gtype)


def test_gvalue_fallback_no_fallback_raises(regress_bitmask_gtype: int) -> None:
    """Without a fallback, gvalue_get_value raises NotImplementedError."""
    from ginext import private

    val = private.gvalue_new_for_gtype(regress_bitmask_gtype)
    with pytest.raises(NotImplementedError):
        private.gvalue_get_value(val)


def test_gvalue_fallback_called_with_correct_gtype(regress_bitmask_gtype: int) -> None:
    """Installed fallback is invoked with the GType and a non-zero pointer."""
    from ginext import private

    val = private.gvalue_new_for_gtype(regress_bitmask_gtype)
    received: list[tuple[int, int]] = []

    def _fallback(gtype: int, gvalue_ptr: int) -> object:
        received.append((gtype, gvalue_ptr))
        return 42

    private.gvalue_set_to_py_fallback(_fallback)
    try:
        result = private.gvalue_get_value(val)
    finally:
        private.gvalue_set_to_py_fallback(None)

    assert result == 42
    assert len(received) == 1
    gtype, ptr = received[0]
    assert gtype == regress_bitmask_gtype
    assert ptr != 0


def test_gvalue_fallback_cleared_restores_error(regress_bitmask_gtype: int) -> None:
    """Clearing the fallback (None) restores the NotImplementedError."""
    from ginext import private

    val = private.gvalue_new_for_gtype(regress_bitmask_gtype)
    private.gvalue_set_to_py_fallback(lambda g, p: "ignored")
    private.gvalue_set_to_py_fallback(None)
    with pytest.raises(NotImplementedError):
        private.gvalue_get_value(val)


def test_gvalue_set_to_py_fallback_rejects_non_callable() -> None:
    """Passing a non-callable (other than None) raises TypeError."""
    from ginext import private

    with pytest.raises(TypeError):
        private.gvalue_set_to_py_fallback(42)  # type: ignore[arg-type]
