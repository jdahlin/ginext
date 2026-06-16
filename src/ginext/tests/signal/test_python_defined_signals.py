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

"""Python-defined GObject signals declared via `GObject.Signal()`.

    class Source(GObject):
        pinged = GObject.Signal()
        bumped = GObject.Signal(int)
        renamed = GObject.Signal(str, str)

Each descriptor registers a real GSignal under the class's GType at
class-creation time; instance access (`src.pinged`) returns a regular
Signal object that uses the same connect / emit / disconnect path as
imported signals.
"""

import itertools
from typing import Any, cast

import pytest

import ginext
from ginext.gobject.gobjectclass import GObject


_seq = itertools.count()


def _name(prefix: str) -> str:
    return f"GinextPySig{prefix}{next(_seq):04d}"


def test_no_payload_signal_emit_and_handler() -> None:
    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    src = Source()
    fires = []
    conn = src.pinged.connect(lambda s: fires.append(1), owner=src)
    src.pinged.emit()
    assert fires == [1]
    conn.disconnect()


def test_int_payload_signal_round_trips_value() -> None:
    class Source(GObject, type_name=_name("Src")):
        bumped = GObject.Signal(int)

    src = Source()
    seen = []
    conn = src.bumped.connect(lambda s, n: seen.append(n), owner=src)
    src.bumped.emit(42)
    src.bumped.emit(-7)
    assert seen == [42, -7]
    conn.disconnect()


def test_string_payload_signal() -> None:
    class Source(GObject, type_name=_name("Src")):
        named = GObject.Signal(str)

    src = Source()
    seen = []
    conn = src.named.connect(lambda s, name: seen.append(name), owner=src)
    src.named.emit("hello")
    assert seen == ["hello"]
    conn.disconnect()


def test_multi_arg_signal() -> None:
    class Source(GObject, type_name=_name("Src")):
        renamed = GObject.Signal(str, str)

    src = Source()
    seen = []
    conn = src.renamed.connect(lambda s, old, new: seen.append((old, new)), owner=src)
    src.renamed.emit("a", "b")
    assert seen == [("a", "b")]
    conn.disconnect()


def test_explicit_name_overrides_attribute_normalisation() -> None:
    class Source(GObject, type_name=_name("Src")):
        weird = GObject.Signal(name="not-a-Python-id")

    src = Source()
    seen = []
    # Look up by the attribute name (Python side); the underlying GSignal
    # uses the explicit override.
    conn = src.weird.connect(lambda s: seen.append(1), owner=src)
    src.weird.emit()
    assert seen == [1]
    conn.disconnect()


def test_underscore_attribute_normalises_to_dash_signal_name() -> None:
    """A descriptor at `item_changed` registers GSignal `item-changed`."""

    class Source(GObject, type_name=_name("Src")):
        item_changed = GObject.Signal()

    src = Source()
    seen = []
    conn = src.item_changed.connect(lambda s: seen.append(1), owner=src)
    src.item_changed.emit()
    assert seen == [1]
    conn.disconnect()


def test_arg_count_mismatch_raises() -> None:
    class Source(GObject, type_name=_name("Src")):
        bumped = GObject.Signal(int)

    src = Source()
    with pytest.raises(TypeError, match="expects 1 argument"):
        src.bumped.emit()
    with pytest.raises(TypeError, match="expects 1 argument"):
        src.bumped.emit(1, 2)


def test_signal_attribute_returns_signal_instance() -> None:
    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    src = Source()
    sig = src.pinged
    assert isinstance(sig, ginext.Signal)


def test_disconnect_via_handle_and_via_signal() -> None:
    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    src = Source()
    conn = src.pinged.connect(lambda s: None, owner=src)
    conn.disconnect()
    # Second disconnect through the signal object is harmless because
    # the handle's state is already cleared.
    src.pinged.disconnect(conn)
    assert not conn.is_connected


def test_python_defined_signal_works_with_constructor_sugar() -> None:
    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    fires = []
    src = cast("Any", Source)(on_pinged=lambda s: fires.append(1))
    src.pinged.emit()
    assert fires == [1]


def test_class_signal_emission_hook_fires_for_all_instances() -> None:
    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    seen = []
    first = Source()
    second = Source()

    def hook(obj: Any) -> bool:
        seen.append(obj)
        return True

    hook_id = first.pinged.add_emission_hook(hook)
    try:
        first.pinged.emit()
        second.pinged.emit()
        assert seen == [first, second]
    finally:
        first.pinged.remove_emission_hook(hook_id)


def test_instance_signal_emission_hook_remove() -> None:
    class Source(GObject, type_name=_name("Src")):
        pinged = GObject.Signal()

    src = Source()
    seen: list[Any] = []

    def _hook(obj: Any) -> bool:
        seen.append(obj)
        return True

    hook_id = src.pinged.add_emission_hook(_hook)
    src.pinged.emit()
    src.pinged.remove_emission_hook(hook_id)
    src.pinged.emit()

    assert seen == [src]


def test_descriptor_repr_includes_name_and_args() -> None:
    class Source(GObject, type_name=_name("Src")):
        bumped = GObject.Signal(int)

    r = repr(Source.bumped)
    assert "bumped" in r
    assert "int" in r
