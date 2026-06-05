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

"""Property-based GObject construction via kwargs.

The plan: generic GObject construction remains property-based:
    obj = SomeObject(prop_name=value)
Internally maps to g_object_new_with_properties().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest


def test_construct_with_gobject_value(unique_type_name: Callable[[str], str]) -> None:
    """A construct property whose type is another GObject class.

    The plan calls out that construct properties accept scalars and
    concrete GObject values in the first pass.
    """
    pytest.importorskip("ginext")
    from ginext import Gio
    from ginext.gobject import gobjectclass as gobject

    gobject_meta: Any = type(gobject.GObject)
    Holder = gobject_meta(
        unique_type_name("Holder"),
        (gobject.GObject,),
        {
            "__annotations__": {"target": Gio.Cancellable},
            "target": gobject.Property(),
        },
    )

    target = Gio.Cancellable()
    holder = Holder(target=target)

    assert holder.target is target
