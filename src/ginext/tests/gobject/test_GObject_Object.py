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

"""
GObjectBase + wrapper registry tests.

Validates:
  - bare GObject construction + wrapping
  - wrapper is an instance of GObjectBase
  - destruction path (Python wrapper gc'd → C GObject unrefed)
  - parallel construction across threads (registry lock + qdata under nogil)
"""

from __future__ import annotations


import gc
import threading
from typing import Any

from ginext import private as _core


_core.require_namespace("GObject", "2.0")


def _new_gobject() -> Any:
    from ginext import GObject

    return GObject.Object()


def is_goi_wrapper(obj: object) -> bool:
    # Every ginext GObject wrapper is an instance of the single GObject base.
    from ginext import private

    return obj is not None and isinstance(obj, private.GObject)


def is_goi_weakref(obj: object) -> bool:
    return callable(obj)


def test_construct_and_wrap() -> None:
    obj = _new_gobject()
    assert is_goi_wrapper(obj)
    assert "GObject" in repr(obj)


def test_distinct_wrappers_for_distinct_gobjects() -> None:
    a = _new_gobject()
    b = _new_gobject()
    assert a is not b
    # The repr includes the GObject's address, which must differ.
    assert repr(a) != repr(b)


def test_wrapper_lifecycle_no_crash() -> None:
    """Construct, drop, GC. Must not crash even with many cycles."""
    for _ in range(2000):
        obj = _new_gobject()
        del obj
    gc.collect()


def test_parallel_construction_under_nogil() -> None:
    """Hammer the wrapper registry from many threads at once. Each thread
    independently constructs new GObjects (so no qdata install contention
    on the same object); the path still exercises ref/unref atomicity and
    the install mutex."""
    # Pre-warm the lazy class resolution so the threads race on the
    # wrapper-registry / qdata path (what this test cares about), not on
    # GIR class resolution.
    _new_gobject()

    n_threads = 8
    per_thread = 500
    barrier = threading.Barrier(n_threads + 1)
    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def runner() -> None:
        try:
            barrier.wait()
            for _ in range(per_thread):
                obj = _new_gobject()
                assert is_goi_wrapper(obj)
        except (AssertionError, RuntimeError, TypeError) as e:
            with errors_lock:
                errors.append(e)

    threads = [threading.Thread(target=runner) for _ in range(n_threads)]
    for t in threads:
        t.start()

    barrier.wait()
    for t in threads:
        t.join()

    assert not errors, errors


def test_gobject_weak_ref_no_callback() -> None:
    """weak_ref() with no callback returns a GObjectWeakRef.
    Calling it returns a wrapper (or None when the GObject is gone)."""
    obj = _new_gobject()
    wr = obj.weak_ref()
    assert is_goi_weakref(wr)
    # While alive, calling returns a wrapper for the same GObject.
    revived = wr()
    assert is_goi_wrapper(revived)
    assert repr(revived) == repr(obj)
    del revived
    del obj
    gc.collect()
    # After the GObject is gone, calling returns None.
    assert wr() is None


def test_gobject_weak_ref_callback_fires() -> None:
    calls: list[tuple[object, ...]] = []

    def cb(*args: object) -> None:
        calls.append(args)

    obj = _new_gobject()
    wr = obj.weak_ref(cb, "tag", 42)
    assert is_goi_weakref(wr)
    # Drop the weak ref handle; the internal self-reference keeps it
    # alive until the notify fires.
    del wr
    del obj
    gc.collect()
    assert calls == [("tag", 42)]


def test_gobject_weak_ref_unref_cancels_notify() -> None:
    fired = []
    obj = _new_gobject()
    wr = obj.weak_ref(lambda: fired.append(1))
    wr.unref()
    # Second unref raises.
    try:
        wr.unref()
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on second unref")
    del obj
    gc.collect()
    assert fired == []


def test_gobject_weak_ref_rejects_non_callable() -> None:
    obj = _new_gobject()
    try:
        obj.weak_ref(42)
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError")
