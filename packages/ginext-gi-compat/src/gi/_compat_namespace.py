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

"""CompatNamespace: Namespace subclass that provides the pygobject-shaped module API.

When gi.repository loads a namespace under PYGOBJECT profile it promotes the
Namespace instance to this subclass via ``namespace.__class__ = CompatNamespace``.
That gives it:
  - ``__repr__``  — ``<module 'GLib' from '/usr/.../GLib-2.0.typelib'>``
  - ``__path__``  — list with the typelib file path (makes ``inspect.getfile`` work)

No monkey-patching of the core ``Namespace`` class happens: only instances that
are promoted to ``CompatNamespace`` get the extra attributes.
"""

from __future__ import annotations

from ginext.namespace import Namespace
from . import _repository_helpers


class CompatNamespace(Namespace):
    def __repr__(self) -> str:
        try:
            path = _repository_helpers.typelib_path(self._name, self._version)
            if path is not None:
                return f"<module '{self.__name__}' from '{path}'>"
        except Exception:
            pass
        return super().__repr__()

    @property  # type: ignore[override]
    def __path__(self) -> list[str]:
        try:
            path = _repository_helpers.typelib_path(self._name, self._version)
            return [path] if path is not None else []
        except Exception:
            return []
