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

"""Gdk.Event union dispatch + nested struct field access.

GdkEvent is a tagged union. Apps reach into a specific arm (motion,
button, key, ...) to read x/y/state/etc. Two pieces have to work:

1. boxed field access: `event.motion` returns a GdkEventMotion struct
   wrapper that aliases into the parent's storage (no copy, no free).
   Lives in src/runtime/object-class.c::boxed_class_getattro.

2. union-arm dispatch: `event.x` looks up the active arm by event type
   and forwards. Declared in `src/goi/_goi/overlays/Gdk-3.0.toml` as a
   `kind = "boxed_union"` class entry; the runtime installs a generic
   discriminator-driven `__getattr__` from `goi.async_helpers.
   _maybe_install_boxed_union`.

These regressed the drawing app's get_event_coords() before the fix.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(scope="module")
def Gdk() -> Any:
    try:
        from ginext import Gdk as _Gdk

        if _Gdk.__version__[0] != 3:
            pytest.skip("requires Gdk-3.0")
        return _Gdk
    except (ImportError, ValueError) as e:
        pytest.skip(f"Gdk 3.0 unavailable: {e}")


def test_event_type_field_reads_as_int(Gdk: Any) -> None:
    """Direct enum-typed field on a GdkEvent boxed (no union dispatch)."""
    ev = Gdk.Event.new(Gdk.EventType.MOTION_NOTIFY)
    assert int(ev.type) == int(Gdk.EventType.MOTION_NOTIFY)


def test_event_motion_is_aliased_struct_wrapper(Gdk: Any) -> None:
    """Nested struct field returns a wrapper sharing parent storage."""
    ev = Gdk.Event.new(Gdk.EventType.MOTION_NOTIFY)
    motion = ev.motion
    assert isinstance(motion, Gdk.EventMotion)
    # Reading any primitive field on the alias must work.
    assert motion.x == 0.0
    assert motion.y == 0.0
    assert motion.state == 0


def test_event_x_dispatches_to_active_union_arm(Gdk: Any) -> None:
    """`event.x` on a MOTION_NOTIFY routes to event.motion.x via the
    Gdk override's __goi_getattr_hook__."""
    ev = Gdk.Event.new(Gdk.EventType.MOTION_NOTIFY)
    assert ev.x == 0.0
    assert ev.y == 0.0
    assert ev.state == 0


def test_event_button_dispatches_to_button_arm(Gdk: Any) -> None:
    """BUTTON_PRESS: scroll/x routes to event.button.* — same pattern,
    different arm. (event.button is the arm itself, not the int field.)"""
    ev = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
    assert ev.x == 0.0
    assert ev.y == 0.0
    # event.button is the GdkEventButton arm wrapper; event.button.button
    # is the actual int button index.
    assert isinstance(ev.button, Gdk.EventButton)
    assert ev.button.button == 0


def test_event_unknown_attr_raises_attribute_error(Gdk: Any) -> None:
    """Unknown attribute on a known-type event must AttributeError, not
    silently return None or recurse."""
    ev = Gdk.Event.new(Gdk.EventType.MOTION_NOTIFY)
    with pytest.raises(AttributeError):
        ev.nonexistent_xyz


def test_aliased_struct_keeps_parent_alive(Gdk: Any) -> None:
    """Drop the parent reference; the aliased substruct must still be
    safe to read because it holds a strong ref to the parent."""
    ev = Gdk.Event.new(Gdk.EventType.MOTION_NOTIFY)
    motion = ev.motion
    del ev  # parent reference released by Python; alias holds its own
    # Field reads after parent-name release must not crash.
    assert motion.x == 0.0


def test_primitive_fields_use_getset_descriptors(Gdk: Any) -> None:
    """Primitive fields are pre-resolved into PyGetSetDef descriptors
    at class build time, so `event.motion.x` is an O(1) tp_dict lookup
    + tag-dispatched memory load instead of an O(N) GIR field walk.
    Pinning this here so a future refactor doesn't quietly drop the
    fast path."""
    desc = Gdk.EventMotion.__dict__.get("x")
    assert desc is not None, "EventMotion.x should be installed as a descriptor"
    # PyDescr_NewGetSet produces a getset_descriptor; the exact type
    # name in CPython is "getset_descriptor".
    assert type(desc).__name__ == "getset_descriptor"


pytestmark = pytest.mark.xdist_group("gtk3")
