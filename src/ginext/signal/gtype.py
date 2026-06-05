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

"""GType resolution for Python-defined signal argument/return annotations."""

from __future__ import annotations

from .. import private


# Map a Python annotation type onto the GType used for a signal arg /
# return value when a class declares `GObject.Signal(int, str)`.
_PRIMITIVE_GTYPE_MAP: dict[type, str] = {
    bool: "gboolean",
    int: "gint",
    float: "gdouble",
    str: "gchararray",
}


def _resolve_signal_gtype(value_type: type | None) -> int:
    """Map a Python annotation type onto the GType (as an int) for a
    Python-defined signal arg/return. None → G_TYPE_NONE.

    Primitive Python types use the same GType mapping as Property
    declarations. GObject wrapper classes resolve via their `gimeta.gtype`.
    `object` (the builtin) maps to G_TYPE_OBJECT, which suits "any
    GObject" arguments and is the most common shape; callers that want
    arbitrary non-GObject Python objects can construct an explicit
    GObject subclass instead.
    """
    if value_type is None:
        return 0  # G_TYPE_NONE
    if value_type is object:
        return private.GIMeta.from_type_name("GObject").gtype
    if value_type == list[str]:
        return private.gstrv_get_type()
    name = _PRIMITIVE_GTYPE_MAP.get(value_type)
    if name is not None:
        return private.GIMeta.from_type_name(name).gtype
    gimeta = value_type.gimeta if hasattr(value_type, "gimeta") else None
    if gimeta is not None and isinstance(gimeta.gtype, int) and gimeta.gtype != 0:
        return gimeta.gtype
    raise TypeError(f"unsupported signal argument type {value_type!r}")
