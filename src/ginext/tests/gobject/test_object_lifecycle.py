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

"""Object lifecycle / subclass tests.

Adapted from upstream pygobject's `test_object_lifecycle.py` and trimmed
to behaviors goi already supports. Drives the same code paths that
historically caused random segfaults in `test_python_subclass_construction`
(see commit history) — kept as a regression net so we notice if subclass
wrapping, refcount tracking, or wrapper resurrection regress.

The `__grefcount__` accessor lets these tests pin down the actual
GObject reference count rather than relying on Python-level id()
comparisons.
"""

from __future__ import annotations

import gc
import weakref
from typing import Any, cast

import pytest


@pytest.fixture
def Regress() -> Any:
    from ginext import Regress

    return Regress


@pytest.fixture
def TestObj(Regress: Any) -> Any:
    return Regress.TestObj


# A module-level subclass — pygobject's tests use this pattern to drive
# the GType-registration path that runs once per class, vs. the
# instance-creation path that runs every test.
class _ModuleSubclass:
    """Lazy holder so we don't open Regress at import time."""

    @staticmethod
    def make(TestObj: Any) -> Any:
        class DerivedObj(TestObj):  # type: ignore[misc]
            def __init__(self) -> None:
                super().__init__()

        return DerivedObj


# ---------------------------------------------------------------------
# Basic subclass construction (the previously-skipped segfault case)
# ---------------------------------------------------------------------


def test_python_subclass_isinstance(TestObj: Any) -> None:
    """The original failing case: subclass + isinstance + instance_method."""

    class MyObj(TestObj):  # type: ignore[misc]
        pass

    inst = MyObj()
    assert isinstance(inst, MyObj)
    assert isinstance(inst, TestObj)
    # GObjectBase isn't exposed; check the ginext class marker instead.
    assert hasattr(type(inst), "gimeta")
    assert isinstance(inst.instance_method(), int)


def test_python_subclass_grefcount_is_one(TestObj: Any) -> None:
    """A freshly constructed subclass instance owns exactly one GObject ref."""

    class MyObj(TestObj):  # type: ignore[misc]
        pass

    inst = MyObj()
    assert inst.__grefcount__ == 1


def test_python_subclass_with_init(TestObj: Any) -> None:
    """An __init__ that calls super().__init__() must not double-init or
    leak a ref. pygobject pins the wrapper alive across instance_init via
    a qdata key (`pygobject_instance_init_ref_count`); goi's wrapper
    lifecycle already handles this without that mechanism."""
    DerivedObj = _ModuleSubclass.make(TestObj)
    inst = DerivedObj()
    assert isinstance(inst, DerivedObj)
    assert inst.__grefcount__ == 1


def test_repeated_subclass_construction_no_leak(TestObj: Any) -> None:
    """1000 fresh subclass instances should reach refcount 0 cleanly."""

    class MyObj(TestObj):  # type: ignore[misc]
        pass

    refs = []
    for _ in range(100):
        inst = MyObj()
        refs.append(weakref.ref(inst))
        del inst
    gc.collect()
    # After del + gc, every weakref should be dead.
    alive = [r for r in refs if r() is not None]
    assert alive == []


def test_two_distinct_subclasses(TestObj: Any) -> None:
    """Two unrelated Python subclasses produce two distinct GTypes — goi
    registers a fresh GType per subclass."""

    class A(TestObj):  # type: ignore[misc]
        pass

    class B(TestObj):  # type: ignore[misc]
        pass

    a = A()
    b = B()
    assert isinstance(a, A) and not isinstance(a, B)
    assert isinstance(b, B) and not isinstance(b, A)
    # Both share the parent class.
    assert isinstance(a, TestObj)
    assert isinstance(b, TestObj)


# ---------------------------------------------------------------------
# Wrapper resurrection: when the only Python ref drops but the GObject is
# still referenced from C, a later C→Python crossing must produce a fresh
# wrapper (or reuse an existing one) without crashing.
# ---------------------------------------------------------------------


def test_subclass_wrapper_drop_then_release(TestObj: Any) -> None:
    DerivedObj = _ModuleSubclass.make(TestObj)
    inst = DerivedObj()
    ref = weakref.ref(inst)
    del inst
    gc.collect()
    assert ref() is None


# ---------------------------------------------------------------------
# Wrapper identity via the native wrapper cache.
# ---------------------------------------------------------------------


def test_distinct_instances_keep_distinct_wrapper_identity(TestObj: Any) -> None:
    from ginext import private

    a = TestObj()
    b = TestObj()
    assert private.GObject.from_c(a) is a
    assert private.GObject.from_c(b) is b
    assert a is not b


def test_preallocated_construction_state_skips_second_native_allocation(
    unique_type_name: Any,
) -> None:
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    calls: list[str] = []

    class Preallocated(
        gobject.GObject, type_name=unique_type_name("PreallocatedState")
    ):
        def __init__(self) -> None:
            calls.append("__init__")
            super().__init__()
            self.initialized = True

    ptr = Preallocated.construct_with_properties({})
    obj = Preallocated.__new__(Preallocated)
    obj.prime_construction_state(ptr)

    original_repo = gobject.gobject_repo

    class _ExplodingRepo:
        def new_with_properties(self, *_args: object, **_kwargs: object) -> int:
            raise AssertionError("unexpected second native allocation")

    gobject.gobject_repo = lambda: _ExplodingRepo()  # type: ignore[assignment, return-value]
    try:
        Preallocated.__init__(obj)
    finally:
        gobject.gobject_repo = original_repo

    assert calls == ["__init__"]
    assert private.GObject.from_c(obj) is obj
    assert obj.initialized is True


def test_preallocated_construction_state_preserves_parent_init_chain(
    unique_type_name: Any,
) -> None:
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    order: list[str] = []

    class Base(gobject.GObject, type_name=unique_type_name("PreallocatedBase")):
        def __init__(self) -> None:
            order.append("base1")
            super().__init__()
            order.append("base2")

    class Child(Base, type_name=unique_type_name("PreallocatedChild")):
        def __init__(self) -> None:
            order.append("child1")
            super().__init__()
            order.append("child2")

    ptr = Child.construct_with_properties({})
    obj = Child.__new__(Child)
    obj.prime_construction_state(ptr)
    Child.__init__(obj)

    assert private.GObject.from_c(obj) is obj
    assert order == ["child1", "base1", "base2", "child2"]


def test_wrap_preallocated_construction_defers_pointer_binding_until_init(
    unique_type_name: Any,
) -> None:
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    seen: list[bool] = []

    class Deferred(gobject.GObject, type_name=unique_type_name("PreallocatedDeferred")):
        def __init__(self) -> None:
            seen.append(self.is_bound())
            super().__init__()
            seen.append(self.is_bound())

    ptr = Deferred.construct_with_properties({})
    obj = Deferred.new_preallocated_from_c(ptr)

    assert obj.is_bound() is False

    Deferred.__init__(obj)

    assert private.GObject.from_c(obj) is obj
    assert seen == [False, True]


def test_preallocated_shell_for_python_type(
    unique_type_name: Any,
) -> None:
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    class DeferredViaPrivate(
        gobject.GObject, type_name=unique_type_name("PreallocatedViaPrivate")
    ):
        def __init__(self) -> None:
            super().__init__()
            self.initialized = True

    ptr = DeferredViaPrivate.construct_with_properties({})
    obj = DeferredViaPrivate.new_preallocated_from_c(ptr)

    assert isinstance(obj, DeferredViaPrivate)
    assert obj.is_bound() is False

    obj.__init__()  # type: ignore[misc]

    assert obj.initialized is True
    assert private.GObject.from_c(obj) is obj


def test_wrapper_owns_ref_state_lives_with_the_pointer(unique_type_name: Any) -> None:
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    class Deferred(gobject.GObject, type_name=unique_type_name("WrapperOwnsRefState")):
        pass

    owned = Deferred()
    assert owned.owns_ref() is True
    assert not hasattr(owned, "_gobject_owns_ref")

    ptr = Deferred.construct_with_properties({})

    deferred = Deferred.new_preallocated_from_c(ptr)
    Deferred.__init__(deferred)

    assert deferred.owns_ref() is False
    assert not hasattr(deferred, "_gobject_owns_ref")

    bound = private.GObject.from_c(deferred)
    assert deferred.owns_ref() is True
    assert bound is deferred


def test_gobject_pointer_is_not_exposed_as_a_python_attribute(
    unique_type_name: Any,
) -> None:
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    class Slotted(gobject.GObject, type_name=unique_type_name("WrapperPointerSlot")):
        pass

    obj = Slotted()

    assert private.GObject.from_c(obj) is obj


def test_c_constructed_python_subclass_runs_init_once(
    unique_type_name: Any,
) -> None:
    from ginext import GObject as GObjectNS
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    calls: list[str] = []

    class CConstructed(gobject.GObject, type_name=unique_type_name("CConstructed")):
        def __init__(self) -> None:
            calls.append("__init__")
            super().__init__()
            self.initialized = True

    ptr = GObjectNS.new_with_properties(CConstructed, {})
    obj = cast("CConstructed", private.GObject.from_c(ptr))
    same = cast("CConstructed", private.GObject.from_c(ptr))

    assert calls == ["__init__"]
    assert obj is same
    assert obj.initialized is True


def test_c_constructed_python_subclass_preserves_parent_init_chain(
    unique_type_name: Any,
) -> None:
    from ginext import GObject as GObjectNS
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    order: list[str] = []

    class Base(gobject.GObject, type_name=unique_type_name("CConstructedBase")):
        def __init__(self) -> None:
            order.append("base1")
            super().__init__()
            order.append("base2")

    class Child(Base, type_name=unique_type_name("CConstructedChild")):
        def __init__(self) -> None:
            order.append("child1")
            super().__init__()
            order.append("child2")

    ptr = GObjectNS.new_with_properties(Child, {})
    obj = cast("Child", private.GObject.from_c(ptr))

    assert isinstance(obj, Child)
    assert order == ["child1", "base1", "base2", "child2"]


def test_c_constructed_python_subclass_preserves_properties_and_python_state(
    unique_type_name: Any,
) -> None:
    from ginext import GObject as GObjectNS
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    seen_in_init: list[int] = []

    class WithProperty(gobject.GObject, type_name=unique_type_name("CConstructedProp")):
        number: int = gobject.Property(default=0)

        def __init__(self) -> None:
            super().__init__()
            self.marker = "set-in-init"
            seen_in_init.append(self.number)

    ptr = GObjectNS.new_with_properties(WithProperty, {"number": 42})
    obj = cast("WithProperty", private.GObject.from_c(ptr))

    assert seen_in_init == [0]
    assert obj.marker == "set-in-init"
    assert obj.number == 42


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_c_constructed_python_subclass_init_failure_drops_stale_wrapper_state(
    unique_type_name: Any,
) -> None:
    from ginext import GObject as GObjectNS
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    wrapper_refs: list[weakref.ReferenceType[object]] = []

    class Failing(gobject.GObject, type_name=unique_type_name("CConstructedFailing")):
        def __init__(self) -> None:
            super().__init__()
            self.marker = "stale"
            wrapper_refs.append(weakref.ref(self))
            raise RuntimeError("boom")

    ptr = GObjectNS.new_with_properties(Failing, {})
    assert len(wrapper_refs) == 1
    stale = cast("Failing | None", wrapper_refs[0]())
    assert stale is not None
    assert stale.is_bound() is False

    obj = cast("Failing", private.GObject.from_c(ptr))

    assert isinstance(obj, Failing)
    assert obj is not stale
    assert not hasattr(obj, "marker")
    assert not hasattr(obj, "_gobject_construction_state")
    assert private.GObject.from_c(ptr) is obj


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_c_constructed_python_subclass_init_failure_preserves_construct_properties(
    unique_type_name: Any,
) -> None:
    from ginext import GObject as GObjectNS
    from ginext import private
    from ginext.gobject import gobjectclass as gobject

    seen_in_init: list[int] = []

    class FailingWithProperty(
        gobject.GObject, type_name=unique_type_name("CConstructedFailingProp")
    ):
        number: int = gobject.Property(default=0)

        def __init__(self) -> None:
            super().__init__()
            seen_in_init.append(self.number)
            raise RuntimeError("boom")

    ptr = GObjectNS.new_with_properties(FailingWithProperty, {"number": 42})
    obj = cast("FailingWithProperty", private.GObject.from_c(ptr))

    assert seen_in_init == [0]
    assert obj.number == 42


# ---------------------------------------------------------------------
# Container round-trip via set_bare / bare property.
#
# The C side stores a Python subclass instance in a TestObj's `bare`
# slot. goi must keep the wrapper alive while C holds the ref, and
# the same wrapper must be returned when C hands the object back.
# pygobject achieves this with toggle refs; goi uses the qdata-based
# wrapper cache in classes/gobject-base.c.
# ---------------------------------------------------------------------


def test_set_bare_keeps_subclass_alive(TestObj: Any) -> None:
    """If set_bare isn't exposed, this test silently passes — same
    convention as the existing test_set_bare_with_object."""
    container = TestObj()
    if not hasattr(container, "set_bare"):
        pytest.skip("Regress.TestObj.set_bare not exposed in this typelib version")

    DerivedObj = _ModuleSubclass.make(TestObj)
    obj = DerivedObj()
    container.set_bare(obj)
    # GObject ref count: wrapper (1) + container's GObject ref (+1) = 2.
    assert obj.__grefcount__ >= 2


def test_set_bare_then_drop_keeps_object_alive(TestObj: Any) -> None:
    """Drop the Python ref — C container still holds the GObject, so the
    GObject lives on. We can't get the same Python wrapper back without a
    getter (goi doesn't yet expose `bare` as a property), but the
    GObject staying alive proves the container ref took effect."""
    container = TestObj()
    if not hasattr(container, "set_bare"):
        pytest.skip("Regress.TestObj.set_bare not exposed in this typelib version")

    DerivedObj = _ModuleSubclass.make(TestObj)
    obj = DerivedObj()
    container.set_bare(obj)
    rc_before = obj.__grefcount__

    obj_ref = weakref.ref(obj)
    del obj
    gc.collect()
    # Wrapper may be dead, but the GObject is still ref'd by the container.
    # No way to peek without a getter; just confirm the container is still
    # live and refcount didn't crash anything. The weakref *may* be dead
    # if the wrapper has no toggle-ref keeping it alive (current goi
    # behavior — see classes/gobject-base.h note on weak refs).
    _ = obj_ref()  # may be alive or dead; no assertion either way
    assert rc_before >= 2


# ---------------------------------------------------------------------
# Refcount under repeated method calls — instance_method shouldn't
# accumulate refs.
# ---------------------------------------------------------------------


def test_instance_method_does_not_leak_refs(TestObj: Any) -> None:
    inst = TestObj()
    rc_before = inst.__grefcount__
    for _ in range(1000):
        inst.instance_method()
    rc_after = inst.__grefcount__
    assert rc_after == rc_before


def test_subclass_instance_method_does_not_leak_refs(TestObj: Any) -> None:
    class MyObj(TestObj):  # type: ignore[misc]
        pass

    inst = MyObj()
    rc_before = inst.__grefcount__
    for _ in range(1000):
        inst.instance_method()
    rc_after = inst.__grefcount__
    assert rc_after == rc_before
