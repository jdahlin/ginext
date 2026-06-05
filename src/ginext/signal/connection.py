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

"""The live signal connection handle returned by `Signal.connect`."""

from __future__ import annotations

import contextlib
import sys
import weakref
from typing import TYPE_CHECKING, Any, Callable, Generator, cast

if TYPE_CHECKING:
    from ..gobject.gobjectclass import GObject


def _gobject_repo() -> Any:
    return sys.modules["ginext"].GObject


class UnownedSignalHandlerWarning(ResourceWarning):
    """Warned when `Signal.connect(cb)` cannot infer an owner.

    Bound methods carry their owner via `__self__`; explicit `owner=`,
    `ginext.static_owner`, or `owner.scoped(...)` declare ownership
    intentionally. Otherwise the closure stays connected until the
    source finalizes, which can keep objects alive longer than the
    logical owner intends.
    """


def _ignore_weakref_finalize(_ref: weakref.ReferenceType[object]) -> None:
    pass


class SignalConnection:
    """Handle returned by `Signal.connect`.

    The source is held weakly via the underlying GObject pointer, so a
    finalized source does not leak through the handle. `disconnect()`
    is a no-op after source finalization.
    """

    __slots__ = (
        "_source_ref",
        "_handler_id",
        "_signal_name",
        "_callback",
        "_after",
        "_once",
        "_owner_ref",
        "_callback_is_weak",
    )
    _callback: weakref.ref[Callable[..., Any]] | Callable[..., Any]

    def __init__(
        self,
        source: "GObject",
        handler_id: int,
        signal_name: str,
        callback: Callable[..., Any],
        *,
        after: bool,
        once: bool,
        owner: GObject | None,
        weak_callback: bool = False,
    ) -> None:
        self._source_ref = weakref.ref(source)
        self._handler_id = handler_id
        self._signal_name = signal_name
        if weak_callback:
            try:
                self._callback = weakref.ref(
                    callback,
                    cast(
                        "Callable[[weakref.ReferenceType[Callable[..., Any]]], None]",
                        _ignore_weakref_finalize,
                    ),
                )
                self._callback_is_weak = True
            except TypeError:
                self._callback = callback
                self._callback_is_weak = False
        else:
            self._callback = callback
            self._callback_is_weak = False
        self._after = after
        self._once = once
        self._owner_ref = weakref.ref(owner) if owner is not None else None

    @property
    def handler_id(self) -> int:
        return self._handler_id

    @property
    def signal_name(self) -> str:
        return self._signal_name

    @property
    def source(self) -> "GObject | None":
        return self._source_ref()

    @property
    def callback(self) -> Callable[..., Any]:
        if self._callback_is_weak:
            return cast("Callable[..., Any]", self._callback())
        return cast("Callable[..., Any]", self._callback)

    @property
    def after(self) -> bool:
        return self._after

    @property
    def once(self) -> bool:
        return self._once

    @property
    def owner(self) -> GObject | None:
        return self._owner_ref() if self._owner_ref is not None else None

    @property
    def is_connected(self) -> bool:
        if self._handler_id == 0:
            return False
        source = self._source_ref()
        if source is None:
            return False

        return bool(
            _gobject_repo().signal_handler_is_connected(source, self._handler_id)
        )

    def disconnect(self) -> None:
        if self._handler_id == 0:
            return
        source = self._source_ref()
        if source is None:
            self._handler_id = 0
            return

        _gobject_repo().signal_handler_disconnect(source, self._handler_id)
        self._handler_id = 0

    @contextlib.contextmanager
    def blocked(self) -> "Generator[SignalConnection, None, None]":
        """Block the handler for the duration of the `with` block.

        Other connections to the same signal still fire; only this
        handler is suppressed. The block/unblock pair is balanced even
        if the body raises.
        """
        source = self._source_ref()
        if self._handler_id == 0 or source is None:
            yield self
            return

        _gobject_repo().signal_handler_block(source, self._handler_id)
        try:
            yield self
        finally:
            source = self._source_ref()
            if self._handler_id != 0 and source is not None:
                _gobject_repo().signal_handler_unblock(source, self._handler_id)

    def __repr__(self) -> str:
        state = "connected" if self.is_connected else "disconnected"
        return f"<SignalConnection id={self._handler_id} {state}>"
