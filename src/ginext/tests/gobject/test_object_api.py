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

import sys
from typing import Any


def test_run_dispose_disconnects_signal_handlers(
    GObject: Any, Property: Any, unique_type_name: Any
) -> None:

    class TestObject(GObject, type_name=unique_type_name("PygDispose")):  # type: ignore[misc, call-arg]
        int_prop: int = Property(default=0)

    obj = TestObject()
    called = []

    def on_notify(*args: object) -> None:
        called.append(args)

    obj.notify("int-prop").connect(on_notify, owner=obj)
    obj.int_prop = 1
    obj.int_prop = 2
    obj.run_dispose()
    assert obj.is_bound() is True
    obj.int_prop = 3
    obj.int_prop = 4

    assert len(called) == 2


def test_notify_unknown_detail_is_allowed(GObject: Any) -> None:
    obj = GObject()
    assert obj.notify("does-not-exist") is not None


def test_regular_object_refcount(GObject: Any) -> None:
    obj = GObject()

    assert obj.__grefcount__ == 1


def test_new_instance_has_expected_python_refs(GObject: Any) -> None:
    obj = GObject()

    if hasattr(sys, "getrefcount"):
        assert sys.getrefcount(obj) == (1 if sys.version_info >= (3, 14) else 2)


def test_freeze_notify_plain_method_keeps_refcount(
    GObject: Any, Property: Any, unique_type_name: Any
) -> None:
    class TestObject(GObject, type_name=unique_type_name("PygFreezePlain")):  # type: ignore[misc, call-arg]
        prop: int = Property(default=0)

    obj = TestObject()

    assert obj.__grefcount__ == 1
    obj.freeze_notify()
    assert obj.__grefcount__ == 1
    obj.thaw_notify()
    assert obj.__grefcount__ == 1


def test_freeze_notify_context(
    GObject: Any, Property: Any, unique_type_name: Any
) -> None:
    class TestObject(GObject, type_name=unique_type_name("PygFreezeContext")):  # type: ignore[misc, call-arg]
        prop: int = Property(default=0)

    obj = TestObject()
    tracking = []
    obj.notify("prop").connect(lambda obj, _pspec: tracking.append(obj.prop), owner=obj)

    obj.prop = 1
    with obj.freeze_notify():
        obj.prop = 2
        obj.prop = 3

    assert tracking == [1, 3]


def test_handler_block_context(
    GObject: Any, Property: Any, unique_type_name: Any
) -> None:
    class TestObject(GObject, type_name=unique_type_name("PygHandlerBlock")):  # type: ignore[misc, call-arg]
        prop: int = Property(default=0)

    obj = TestObject()
    tracking = []
    handler = obj.notify("prop").connect(
        lambda obj, _pspec: tracking.append(obj.prop), owner=obj
    )

    obj.prop = 1
    with obj.handler_block(handler):
        obj.prop = 2

    assert tracking == [1]
