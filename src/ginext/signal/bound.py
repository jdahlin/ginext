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

"""The bound ``Signal`` object — the connect/emit/disconnect surface
returned when a signal is accessed on an instance."""

from __future__ import annotations

import inspect
import warnings
from typing import TYPE_CHECKING, Any, Callable, Protocol, cast

from .. import features
from .adapt import (
    _SIGNAL_ARG_LIMIT_ATTR,
    _accepted_signal_arg_count,
    _enclosed_gobject_owners,
    _infer_owner,
    _is_gobject_wrapper,
)
from .connection import SignalConnection, UnownedSignalHandlerWarning
from .emission_hook import add_emission_hook, remove_emission_hook
from .scoped import _OWNER_UNSET, ScopedCallable, _WeakBoundCallable, static_owner

if TYPE_CHECKING:
    from ..gobject.gobjectclass import GObject
    from ginext.GIRepository import SignalInfo


class _PropertyDetail(Protocol):
    name: str


class Signal:
    """

    This object is representing a signal, both inherited and user defined on an object, ie:

    button.clicked
    window.activate

    Most common way of interacting is via the connect() method, but it also supports emit() and disconnect().

    """

    __slots__ = ("_source", "_name", "_info", "_method", "_arg_gtypes")

    def __init__(
        self,
        source: "GObject",
        name: str,
        info: SignalInfo | None,
        method: Callable[..., Any] | None = None,
        *,
        arg_gtypes: tuple[int, ...] | None = None,
    ) -> None:
        self._source = source
        self._name = name
        self._info = info
        self._method = method
        # For Python-defined signals, info is None; arg_gtypes carries
        # the C-side GTypes needed by g_signal_emitv when args are
        # passed. For imported signals, arg_gtypes stays None and the
        # GISignalInfo capsule supplies the per-arg type info instead.
        self._arg_gtypes = arg_gtypes

    def __repr__(self) -> str:
        cls_name = type(self._source).__name__
        suffix = " (callable)" if self._method is not None else ""
        return f"<Signal {cls_name}.{self._name}{suffix}>"

    def _source_ptr(self) -> int:
        if not self._source.is_bound():
            module = type(self._source).__module__
            module = module.removeprefix("ginext.").removeprefix("gi.repository.")
            expected = f"{module}.{type(self._source).__name__}"
            raise TypeError(
                f"expected a {expected}, but got {object.__repr__(self._source)}"
            )
        return 0

    def _detail_signal(self, detail: object) -> "Signal":
        from ..gobject.properties import PropertyBase as Property

        self._source_ptr()
        if isinstance(detail, str):
            detail_str = detail.replace("_", "-")
        elif isinstance(detail, Property) or hasattr(detail, "pspec"):
            detail_str = str(cast("Any", detail).name).replace("_", "-")
        else:
            raise TypeError(
                f"signal detail must be str or Property, got {type(detail).__name__}"
            )
        return Signal(
            self._source,
            f"{self._name}::{detail_str}",
            self._info,
            None,
            arg_gtypes=self._arg_gtypes,
        )

    def detail_signal(self, detail: object) -> "Signal":
        return self._detail_signal(detail)

    def __getitem__(self, detail: object) -> "Signal":
        return self._detail_signal(detail)

    def __call__(self, *args: object, **kwargs: object) -> object:
        if self._name == "notify" and len(args) == 1 and not kwargs:
            detail_signal = self._detail_signal(args[0])
            if self._method is not None and features.is_enabled(
                features.OLD_SIGNAL_API
            ):
                self._method(self._source, args[0])
            return detail_signal
        # A signal that backs a real method (e.g. Gtk.Widget.activate) calls
        # the method. Otherwise, an action signal (G_SIGNAL_ACTION — e.g.
        # Gtk.Button "clicked") may be emitted by calling it; this comes from
        # the signal's flags, not from any overlay. A plain signal is not
        # callable.
        if self._method is not None:
            return self._method(self._source, *args, **kwargs)
        if self._source.signal_is_action(self._name):
            return self.emit(*args)
        cls_name = type(self._source).__name__
        raise TypeError(f"{cls_name}.{self._name!r} is a signal, not a method")

    def connect(
        self,
        callback: Callable[..., Any],
        *,
        after: bool = False,
        once: bool = False,
        owner: Any = _OWNER_UNSET,
        _weak_callback_record: bool = False,
    ) -> SignalConnection:
        # Owner resolution. static_owner suppresses the warning without
        # passing an owner pointer; an explicit owner= must be a GObject
        # wrapper (imported or Python-defined); otherwise we infer from
        # __self__ and warn if we still come up empty.
        if owner is static_owner:
            resolved_owner: Any | None = None
        elif owner is _OWNER_UNSET:
            resolved_owner = _infer_owner(callback)
            if resolved_owner is None:
                # Ambiguous multi-owner closure (a lambda/function that
                # captures more than one GObject wrapper) must be
                # rejected. Picking one silently would surprise users
                # whose intent was the OTHER object; warning isn't
                # enough because the wrong choice is invisible.
                candidates = _enclosed_gobject_owners(callback)
                if len(candidates) > 1:
                    raise TypeError(
                        f"cannot infer signal owner for {callback!r}: "
                        f"closure captures {len(candidates)} GObject "
                        f"wrappers ({', '.join(type(c).__name__ for c in candidates)}). "
                        "Pass owner= explicitly, use ginext.static_owner, "
                        "or self.scoped(callback)."
                    )
                warnings.warn(
                    f"connecting {callback!r} to "
                    f"{type(self._source).__name__}.{self._name!r} "
                    "without an owner; the handler stays connected until "
                    "the source is finalized. Pass owner=..., use "
                    "ginext.static_owner, or self.scoped(callback).",
                    UnownedSignalHandlerWarning,
                    stacklevel=2,
                )
        else:
            if not _is_gobject_wrapper(owner):
                raise TypeError(
                    f"owner= must be a GObject wrapper or "
                    f"ginext.static_owner, got {type(owner).__name__}"
                )
            resolved_owner = owner

        # Bound method whose host IS the resolved owner: substitute a
        # weak wrapper so the closure doesn't pin its own owner. Python
        # computes the runtime signal-arg prefix here; the C closure
        # marshal enforces it before invoking the target callable.
        weaken = (
            resolved_owner is not None
            and inspect.ismethod(callback)
            and callback.__self__ is resolved_owner
        )
        declared_arg_limit = getattr(callback, _SIGNAL_ARG_LIMIT_ATTR, _OWNER_UNSET)
        if declared_arg_limit is not _OWNER_UNSET:
            signal_arg_limit = declared_arg_limit
        elif isinstance(callback, ScopedCallable):
            signal_arg_limit = callback._signal_arg_count
        else:
            signal_arg_limit = _accepted_signal_arg_count(callback)

        target_callable = (
            _WeakBoundCallable(cast("Any", callback), None) if weaken else callback
        )
        handler_id = self._source.signal_connect(
            self._name,
            target_callable,
            after,
            once,
            resolved_owner,
            self._info,
            -1 if signal_arg_limit is None else int(cast("Any", signal_arg_limit)),
        )
        return SignalConnection(
            self._source,
            handler_id,
            self._name,
            callback,
            after=after,
            once=once,
            owner=resolved_owner,
            weak_callback=_weak_callback_record,
        )

    def disconnect(self, connection: SignalConnection) -> None:
        connection.disconnect()

    def emit(self, *args: object) -> object:
        self._source_ptr()
        default_result = None
        # Validate arity for Python-defined signals on the Python side
        # so a zero-arg call to a signal that declared args raises
        # cleanly (g_signal_emit would otherwise deliver uninitialised
        # GValues to handlers).
        if self._arg_gtypes is not None:
            expected = len(self._arg_gtypes)
            if len(args) != expected:
                raise TypeError(
                    f"signal {self._name!r} expects {expected} argument(s), "
                    f"got {len(args)}"
                )
            default_name = "do_" + self._name.replace("-", "_")
            default_handler = getattr(self._source, default_name, None)
            if callable(default_handler):
                default_result = default_handler(*args)
        if not args:
            result = self._source.signal_emit(self._name)
            return default_result if result is None else result
        if self._info is not None:
            return self._source.signal_emit(self._name, self._info, args)
        if self._arg_gtypes is None:
            raise NotImplementedError(
                f"signal {self._name!r} has no type info recorded; cannot marshal args"
            )
        result = self._source.signal_emit_with_gtypes(
            self._name, self._arg_gtypes, args
        )
        return default_result if result is None else result

    def add_emission_hook(self, callback: Callable[..., Any]) -> int:
        return add_emission_hook(type(self._source).gimeta.gtype, self._name, callback)

    def remove_emission_hook(self, hook_id: int) -> None:
        remove_emission_hook(type(self._source).gimeta.gtype, self._name, hook_id)
