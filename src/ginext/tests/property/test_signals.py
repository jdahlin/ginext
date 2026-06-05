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

from typing import Any


def test_setting_property_emits_notify(make_property_class: Any) -> None:
    cls = make_property_class(int, name="count", default=0)
    seen = []
    obj = cls()
    obj.notify("count").connect(lambda source, pspec: seen.append(source.count))
    obj.count = 5
    assert seen == [5]


def test_setting_to_same_value_still_notifies(make_property_class: Any) -> None:
    cls = make_property_class(int, default=7)
    seen = []
    obj = cls()
    obj.notify("x").connect(lambda *_: seen.append(1))
    obj.x = 7
    assert len(seen) == 1


def test_notify_pspec_argument_matches_property(make_property_class: Any) -> None:
    cls = make_property_class(str, name="title", default="")
    received = []
    obj = cls()
    obj.notify("title").connect(lambda source, pspec: received.append(pspec.name))
    obj.title = "hello"
    assert received == ["title"]


def test_notify_detail_uses_canonical_name(make_property_class: Any) -> None:
    cls = make_property_class(int, name="my_field", default=0)
    seen = []
    obj = cls()
    obj.notify("my-field").connect(lambda *_: seen.append("hyphen"))
    obj.notify("my_field").connect(lambda *_: seen.append("underscore"))
    obj.my_field = 1
    assert sorted(seen) == ["hyphen", "underscore"]


def test_freeze_thaw_coalesces_notifies(make_property_class: Any) -> None:
    cls = make_property_class(int, default=0)
    seen = []
    obj = cls()
    obj.notify("x").connect(lambda *_: seen.append(1))
    obj.freeze_notify()
    for value in range(10):
        obj.x = value
    obj.thaw_notify()
    assert len(seen) == 1


def test_handler_disconnect_stops_notifications(make_property_class: Any) -> None:
    cls = make_property_class(int, default=0)
    obj = cls()
    seen = []
    handler = obj.notify("x").connect(lambda *_: seen.append(1))
    obj.x = 1
    handler.disconnect()
    obj.x = 2
    assert seen == [1]


def test_inherited_property_emits_notify_on_subclass(
    GObject: Any, Property: Any
) -> None:
    class A(GObject):  # type: ignore[misc]
        x: int = Property(default=0)

    class B(A):
        pass

    obj = B()
    seen = []
    obj.notify("x").connect(lambda *_: seen.append(1))
    obj.x = 5
    assert seen == [1]
