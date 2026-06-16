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

"""`SignalDescriptor` — the class-level `GObject.Signal(...)` declaration.

`__set_name__` captures the attribute name; after the owning class is
registered, `_register` resolves arg gtypes and installs the signal.
Instance access (`__get__`) returns a bound :class:`~ginext.signal.bound.Signal`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, overload

from .. import features, private
from .bound import Signal
from .gtype import _resolve_signal_gtype

if TYPE_CHECKING:
    from ..gobject.gobjectclass import GObject
    from ginext.GIRepository import SignalInfo


class SignalDescriptor:
    """Class-level descriptor declaring a Python-defined GObject signal.

    Usage:

        class Source(GObject):
            pinged = GObject.Signal()
            item_changed = GObject.Signal(object)
            renamed = GObject.Signal(str, str, name="renamed")

    `__set_name__` captures the python attribute name (and derives the
    GObject signal name via `_` → `-`). After `__init_subclass__` runs
    register_gobject_subclass, gobject.GObject._register_python_signals
    iterates these descriptors and calls gimeta.register_signal for
    each. The resulting signal_id + arg gtypes are stored on the
    descriptor; instance access then returns a regular Signal object.
    """

    def __init__(
        self,
        *arg_types: type,
        name: str | None = None,
        return_type: type | None = None,
    ) -> None:
        self._arg_types = arg_types
        self._explicit_name = name
        self._return_type = return_type
        self._py_name: str | None = None
        self._gobject_name: str | None = None
        self._signal_id = 0
        self._arg_gtypes: tuple[int, ...] | None = ()
        self._owner_gtype = 0
        self._owner_gimeta: private.GIMeta | None = None
        self._info: SignalInfo | None = None
        self._method: Callable[..., Any] | None = None
        self._is_imported = False

    @classmethod
    def imported(
        cls,
        name: str,
        info: SignalInfo,
        method: Callable[..., Any],
    ) -> "SignalDescriptor":
        descriptor = cls(name=name.replace("_", "-"))
        descriptor._py_name = name
        descriptor._gobject_name = name.replace("_", "-")
        descriptor._arg_gtypes = None
        descriptor._info = info
        descriptor._method = method
        descriptor._is_imported = True
        return descriptor

    def __set_name__(self, owner: type, name: str) -> None:
        self._py_name = name
        self._gobject_name = self._explicit_name or name.replace("_", "-")

    def _register(self, gimeta: private.GIMeta) -> None:
        """Resolve arg gtypes and call gimeta.register_signal. Idempotent —
        running on a duplicate class is a no-op."""
        if self._signal_id != 0:
            return
        if self._gobject_name is None:
            raise RuntimeError(
                "Signal descriptor never received __set_name__; "
                "is it bound as a class attribute?"
            )
        return_gtype = _resolve_signal_gtype(self._return_type)
        self._arg_gtypes = tuple(_resolve_signal_gtype(t) for t in self._arg_types)
        self._signal_id = gimeta.register_signal(
            self._gobject_name,
            return_gtype,
            self._arg_gtypes,
            *self._extra_register_args(),
        )
        self._owner_gtype = gimeta.gtype
        self._owner_gimeta = gimeta

    def _extra_register_args(self) -> tuple[object, ...]:
        return ()

    def matches_name(self, name: str) -> bool:
        if self._py_name == name:
            return True
        if self._gobject_name is not None and self._gobject_name.replace("-", "_") == name:
            return True
        return False

    def attribute_name(self) -> str | None:
        if self._py_name is not None:
            return self._py_name
        if self._gobject_name is not None:
            return self._gobject_name.replace("-", "_")
        return None

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> SignalDescriptor: ...

    @overload
    def __get__(self, obj: GObject, objtype: type | None = None) -> Signal: ...

    def __get__(
        self, obj: GObject | None, objtype: type | None = None
    ) -> Signal | Callable[..., Any] | SignalDescriptor:
        if obj is None:
            return self._method or self
        if self._is_imported and not features.is_enabled(features.NEW_SIGNAL_API):
            raise AttributeError(self._py_name or self._gobject_name or "signal")
        assert self._gobject_name is not None
        return Signal(
            obj,
            self._gobject_name,
            self._info,
            self._method,
            arg_gtypes=self._arg_gtypes,
        )

    def add_emission_hook(self, callback: Callable[..., Any]) -> int:
        if self._owner_gimeta is None or self._gobject_name is None:
            raise TypeError("signal is not registered")
        return self._owner_gimeta.add_emission_hook(self._gobject_name, callback)

    def remove_emission_hook(self, hook_id: int) -> None:
        if self._owner_gimeta is None or self._gobject_name is None:
            raise TypeError("signal is not registered")
        self._owner_gimeta.remove_emission_hook(self._gobject_name, hook_id)

    def __repr__(self) -> str:
        types_repr = ", ".join(t.__name__ for t in self._arg_types)
        return (
            f"<GObject.Signal {self._gobject_name or self._py_name or '?'}"
            f"({types_repr})>"
        )
