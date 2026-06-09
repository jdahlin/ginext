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

"""pygobject's `obj.props` property bag.

`obj.props.some_name` reads/writes the GObject property `some-name`. This is
pygobject's accessor shape, not ginext's native surface (declared properties are
plain attributes; introspected ones go through get_property/set_property), so
the proxy and the `props` property live in the compat package and are installed
onto the GObject class by `repository._install_gobject_props` when the
pygobject-compat layer is active.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ginext.gobject.gobjectclass import GObject


class PropsProxy:
    __slots__ = ("_obj",)
    _obj: "GObject"

    def __init__(self, obj: "GObject") -> None:
        super().__setattr__("_obj", obj)

    def __getattr__(self, name: str) -> object:
        return self._obj.get_property(name)

    def __setattr__(self, name: str, value: object) -> None:
        self._obj.set_property(name, value)

    def __dir__(self) -> list[str]:
        pspecs = type(self._obj).gimeta.pspecs
        return sorted(name.replace("-", "_") for name in pspecs)


def _props(self: "GObject") -> PropsProxy:
    return PropsProxy(self)


def install_props(gobject_cls: type) -> None:
    gobject_cls.props = property(_props)  # type: ignore[attr-defined]
