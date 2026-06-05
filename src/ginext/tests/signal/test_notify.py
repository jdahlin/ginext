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

"""Detailed notify binding via ``obj.notify(detail)``.

Covers:
- `obj.notify("name").connect(cb)` connecting to notify::name (string key)
- `obj.notify(Cls.prop).connect(cb)` connecting via Property descriptor
- detail filtering: notify::a does not fire when notify::b is emitted
- setting a Property auto-emits notify::<name>

Note: `from __future__ import annotations` is intentionally NOT enabled
here — register_gobject_subclass reads `cls.__annotations__[name]` and
needs the actual type objects, not their stringified form.
"""

import itertools
from typing import Any

import pytest

from ginext.gobject.gobjectclass import GObject, Property


_seq = itertools.count()


def _unique_type_name(prefix: str) -> str:
    return f"GinextNotify{prefix}{next(_seq):04d}"


@pytest.fixture
def MyObj() -> Any:
    class _Obj(GObject, type_name=_unique_type_name("MyObj")):
        title: str = Property(default="initial")
        count: int = Property(default=0)

    return _Obj


def test_notify_signal_by_name(MyObj: Any) -> None:
    obj = MyObj()
    seen = []
    conn = obj.notify("title").connect(lambda src: seen.append(src is obj), owner=obj)
    obj.title = "updated"
    assert seen == [True]
    conn.disconnect()


def test_notify_signal_by_descriptor(MyObj: Any) -> None:
    obj = MyObj()
    seen = []
    conn = obj.notify(MyObj.title).connect(
        lambda src: seen.append("via-desc"), owner=obj
    )
    obj.title = "updated"
    assert seen == ["via-desc"]
    conn.disconnect()


def test_property_set_auto_emits_notify(MyObj: Any) -> None:
    """Setting a GObject property through the Property descriptor triggers
    g_object_notify_by_pspec on the C side, so handlers attached via
    `obj.notify(name).connect(...)` fire as a side effect of the
    assignment — the same way they would under g_object_set_property."""
    obj = MyObj()
    seen = []
    conn = obj.notify("title").connect(lambda src: seen.append("fired"), owner=obj)
    obj.title = "updated"
    assert seen == ["fired"]
    assert obj.title == "updated"
    conn.disconnect()


def test_detail_filter_isolates_properties(MyObj: Any) -> None:
    """A handler on notify::title must not fire for notify::count."""
    obj = MyObj()
    title_fires = []
    count_fires = []
    c_title = obj.notify("title").connect(lambda src: title_fires.append(1), owner=obj)
    c_count = obj.notify("count").connect(lambda src: count_fires.append(1), owner=obj)
    obj.count = 1
    assert title_fires == []
    assert count_fires == [1]
    obj.title = "changed"
    assert title_fires == [1]
    assert count_fires == [1]
    c_title.disconnect()
    c_count.disconnect()


def test_pspec_argument_available_to_handler(MyObj: Any) -> None:
    """The notify signal carries a GParamSpec as its second arg. A
    two-arg handler receives both source and pspec."""
    obj = MyObj()
    seen = []
    conn = obj.notify("title").connect(lambda src, pspec: seen.append(pspec), owner=obj)
    obj.title = "updated"
    assert len(seen) == 1
    # The wrapper exposes at least a class identity — pygi_param_spec_new
    # returns a ginext.private.ParamSpec wrapper.
    assert seen[0] is not None
    conn.disconnect()


def test_notify_signal_attr_repr_is_callable(MyObj: Any) -> None:
    """The detail-selected notify object is a connectable bound Signal."""
    obj = MyObj()
    assert "<Signal" in repr(obj.notify("title"))


def test_unknown_detail_string_does_nothing_useful(MyObj: Any) -> None:
    """Connecting to a non-existent property's notify::detail is allowed
    (GObject accepts any detail quark) but the handler simply never fires
    when other properties are notified."""
    obj = MyObj()
    seen = []
    conn = obj.notify("does-not-exist").connect(lambda src: seen.append(1), owner=obj)
    obj.title = "updated"
    assert seen == []
    conn.disconnect()


def test_invalid_detail_type_raises(MyObj: Any) -> None:
    obj = MyObj()
    with pytest.raises(TypeError, match="detail must be str or Property"):
        obj.notify(42)


def test_disconnect_via_handle(MyObj: Any) -> None:
    obj = MyObj()
    seen = []
    conn = obj.notify("title").connect(lambda src: seen.append(1), owner=obj)
    conn.disconnect()
    obj.title = "updated"
    assert seen == []
