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

"""Callback introspection and adaptation for signal connection.

Turns a user callback into something connectable: positional-arity
inspection (how many signal args to forward), owner inference for the
ownership policy, and the `on_<signal>=` constructor-handler helpers.
"""

from __future__ import annotations

import inspect
import types
import difflib
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    NamedTuple,
    Protocol,
    cast,
    runtime_checkable,
)

from .. import private

if TYPE_CHECKING:
    pass

_SIGNAL_ARG_LIMIT_ATTR = "__ginext_signal_arg_limit__"


@runtime_checkable
class _HasGIMeta(Protocol):
    gimeta: private.GIMeta


@runtime_checkable
class _ConnectableSignal(Protocol):
    def connect(self, callback: Callable[..., Any], **kwargs: object) -> object: ...


class _CallbackArity(NamedTuple):
    required_positional: int
    accepted_positional: int | None


def _split_constructor_kwargs(
    kwargs: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Split a constructor kwargs dict into (properties, handlers).

    Keys starting with ``on_`` are treated as signal-handler kwargs;
    everything else is a property. The ``on_`` prefix is stripped from
    handler keys so the caller can look up the signal by its underscore
    name (``on_clicked`` → look up ``clicked``)."""
    properties: dict[str, object] = {}
    handlers: dict[str, object] = {}
    for key, value in kwargs.items():
        if key.startswith("on_") and len(key) > 3:
            handlers[key[3:]] = value
        else:
            properties[key] = value
    return properties, handlers


def _connect_constructor_handler(
    owner: object, signal_attr_name: str, callback: object
) -> None:
    """Connect a callback declared as `on_<signal_attr_name>=callback`.

    The owner is the newly-constructed instance, so signal lifetime is
    tied to it automatically. Plain callable values only — advanced
    shapes (after, once, scoped extras) go through post-construction
    `obj.signal.connect(...)`.
    """
    if not callable(callback):
        raise TypeError(
            f"on_{signal_attr_name}= must be callable, got {type(callback).__name__}"
        )
    cb: Callable[..., Any] = cast("Callable[..., Any]", callback)
    cls = type(owner)
    if not isinstance(cls, _HasGIMeta):
        raise TypeError(f"{type(owner).__name__} has no GObject metadata")
    gimeta = cls.gimeta
    infos = gimeta.signal_infos
    if signal_attr_name not in infos:
        available = sorted(infos)
        close = difflib.get_close_matches(signal_attr_name, available, n=3)
        hint = f"; did you mean {close!r}?" if close else ""
        raise TypeError(
            f"{cls.__name__} has no signal named "
            f"{signal_attr_name!r} (from on_{signal_attr_name}=){hint}"
        )
    sig = getattr(owner, signal_attr_name)
    if not isinstance(sig, _ConnectableSignal):
        raise TypeError(
            f"{cls.__name__}.{signal_attr_name!r} is not a connectable signal"
        )
    sig.connect(cb, owner=owner)


def _callback_positional_arity(callback: Callable[..., Any]) -> _CallbackArity | None:
    """Return positional arity for `callback`, or None if uninspectable.

    `accepted_positional is None` means the callback takes ``*args``:
    pass all runtime signal args and let the callable decide what to do.
    `None` return means `inspect.signature` couldn't introspect the
    callable (builtins, opaque C callables); callers should also pass
    everything and let the callable raise naturally if needed.
    """
    try:
        sig = inspect.signature(callback)
    except (TypeError, ValueError):
        return None
    required = 0
    accepted = 0
    for p in sig.parameters.values():
        if p.kind is inspect.Parameter.VAR_POSITIONAL:
            return _CallbackArity(required, None)
        if p.kind not in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            continue
        accepted += 1
        if p.default is inspect.Parameter.empty:
            required += 1
    return _CallbackArity(required, accepted)


def _callback_arity(callback: Callable[..., Any]) -> int | None:
    """Return the max positional args `callback` accepts, or None.

    Kept as the small helper used by weak bound-method adapters and
    tests. Defaults count as accepted positional args; missing required
    args are never synthesized.
    """
    arity = _callback_positional_arity(callback)
    if arity is None:
        return None
    return arity.accepted_positional


def _accepted_signal_arg_count(
    callback: Callable[..., Any], extra_positional_args: int = 0
) -> int | None:
    """Return how many runtime signal args may be forwarded.

    Explicit extra positional args (from `scoped()` or compatibility
    user_data wrappers) are appended after retained signal args and must
    be preserved. Therefore they consume slots from the callable's
    accepted positional arity before runtime signal args are considered.
    """
    arity = _callback_positional_arity(callback)
    if arity is None or arity.accepted_positional is None:
        return None
    return max(0, arity.accepted_positional - extra_positional_args)


def _make_arg_adapter(callback: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap `callback` so it only receives a positional prefix of the signal args.

    The closure marshal always passes the full signal-arg tuple. Most
    handlers accept a positional prefix: `lambda: ...` for zero args,
    `lambda src: ...` for source-only, etc. The adapter inspects the
    callback's signature once at connect time and stores the resulting
    wrapper in the GClosure; `SignalConnection.callback` keeps the
    original.

    Varargs/uninspectable callbacks are returned unchanged.
    """
    n = _accepted_signal_arg_count(callback)
    if n is None:
        return callback
    if n == 0:

        def _adapter(*_signal_args: object) -> object:
            return callback()
    else:

        def _adapter(*signal_args: object) -> object:
            return callback(*signal_args[:n])

    return _adapter


def _is_gobject_wrapper(obj: object) -> bool:
    """True if obj is a bound ginext GObject wrapper."""
    return isinstance(obj, private.GObject) and obj.is_bound()


def _infer_owner(callback: Callable[..., Any]) -> Any | None:
    """Return the owner GObject wrapper for a bound-method callback, or None.

    Recognised shapes:
    - `obj.method` → bound method whose `__self__` is the owner
    - `ScopedCallable(...)` → has `__self__` set to the scoped owner
    Anything else (lambda, free function, partial, callable object)
    returns None and triggers the unowned warning path.
    """
    inferred = callback.__self__ if hasattr(callback, "__self__") else None
    if inferred is not None and _is_gobject_wrapper(inferred):
        return inferred
    return None


def _enclosed_gobject_owners(callback: Callable[..., Any]) -> list[object]:
    """Return the list of GObject wrappers captured by `callback`'s closure.

    Walks `callback.__closure__` cells (skipping unbound ones) and keeps
    the values that look like ginext GObject wrappers. Used to detect
    the ambiguous-multi-owner case where a lambda closes over more than
    one GObject and the inference path cannot pick one.
    """
    if not isinstance(callback, types.FunctionType):
        return []
    cells = callback.__closure__
    if not cells:
        return []
    found: list[object] = []
    seen_ids: set[int] = set()
    for cell in cells:
        try:
            value = cell.cell_contents
        except ValueError:
            continue
        if _is_gobject_wrapper(value) and id(value) not in seen_ids:
            seen_ids.add(id(value))
            found.append(value)
    return found


def _make_cell(value: object) -> types.CellType:
    def inner() -> object:
        return value

    assert inner.__closure__ is not None
    return inner.__closure__[0]
