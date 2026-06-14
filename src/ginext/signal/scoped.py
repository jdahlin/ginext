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

"""Handler ownership and weak-binding.

The owner-policy sentinels (`static_owner`, `_OWNER_UNSET`) and the weak
callables that let a handler's lifetime track an owner without the
closure pinning it alive (`ScopedCallable`, the weak bound-method wrappers).
"""

from __future__ import annotations

import inspect
import types
import weakref
from typing import TYPE_CHECKING, Any, Callable

from .adapt import _accepted_signal_arg_count, _make_cell

if TYPE_CHECKING:
    from ..gobject.gobjectclass import GObject


class _StaticOwnerSentinel:
    """Marker value for `owner=ginext.static_owner`.

    Selecting this disables both owner inference *and* the unowned
    warning; the closure is intentionally process-lifetime."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "ginext.static_owner"


static_owner = _StaticOwnerSentinel()


_OWNER_UNSET = object()


class _WeakMethodCallable:
    __slots__ = ("_func", "_self_ref")

    def __init__(self, bound_method: types.MethodType) -> None:
        self._func = bound_method.__func__
        self._self_ref = weakref.ref(bound_method.__self__)

    def __call__(self, *args: object, **kwargs: object) -> object:
        host = self._self_ref()
        if host is None:
            return None
        return self._func(host, *args, **kwargs)

    def __repr__(self) -> str:
        host = self._self_ref()
        func_name = (
            self._func.__qualname__
            if hasattr(self._func, "__qualname__")
            else repr(self._func)
        )
        return f"<weak-method {func_name} on {host!r}>"


def _weaken_scoped_callback(
    callback: Callable[..., Any], owner: object
) -> Callable[..., Any]:
    if inspect.ismethod(callback) and callback.__self__ is not None:
        return _WeakMethodCallable(callback)

    if (
        not isinstance(callback, types.FunctionType)
        or callback.__closure__ is None
        or callback.__name__ != "<lambda>"
    ):
        return callback

    changed = False
    cells: list[types.CellType] = []
    for cell in callback.__closure__:
        try:
            value = cell.cell_contents
        except ValueError:
            cells.append(cell)
            continue
        if value is owner:
            cells.append(_make_cell(weakref.proxy(owner)))
            changed = True
        else:
            cells.append(cell)

    if not changed:
        return callback

    weakened = types.FunctionType(
        callback.__code__,
        callback.__globals__,
        callback.__name__,
        callback.__defaults__,
        tuple(cells),
    )
    weakened.__kwdefaults__ = callback.__kwdefaults__
    weakened.__annotations__ = dict(callback.__annotations__)
    try:
        callback_attrs = vars(callback)
    except TypeError:
        callback_attrs = {}
    vars(weakened).update(callback_attrs)
    weakened.__module__ = callback.__module__
    weakened.__qualname__ = callback.__qualname__
    return weakened


class ScopedCallable:
    """Callback adapter that binds an owner weakly and optional trailing args.

    Created by `GObject.scoped(callback, *args, **kwargs)`. Its
    `__self__` property exposes the owner so `Signal.connect`'s
    inference picks it up. The owner is held *weakly* — the closure
    that carries this wrapper does not pin the owner. When the owner
    dies, calls become no-ops; the closure's owner-weak-notify still
    disconnects the handler at the GObject layer too.
    """

    __slots__ = (
        "_owner_ref",
        "_callback",
        "_extra_args",
        "_extra_kwargs",
        "_signal_arg_count",
    )

    def __init__(
        self,
        owner: "GObject",
        callback: Callable[..., Any],
        *args: object,
        **kwargs: object,
    ) -> None:
        self._owner_ref = weakref.ref(owner)
        self._callback = _weaken_scoped_callback(callback, owner)
        self._extra_args = args
        self._extra_kwargs = kwargs
        self._signal_arg_count = _accepted_signal_arg_count(
            self._callback, len(self._extra_args)
        )

    @property
    def __self__(self) -> GObject | None:
        """Live owner reference (None after owner finalization).

        Exposed for `Signal.connect`'s `_infer_owner` path; at connect
        time the owner is alive so this returns it. After the owner
        dies, `_is_gobject_wrapper(None)` is False, so any inference
        re-attempt at a later connect would fall through to the unowned
        warning rather than mistakenly weakening a dead wrapper.
        """
        return self._owner_ref()

    def __call__(self, *signal_args: object) -> object:
        host = self._owner_ref()
        if host is None:
            return None
        return self._callback(*signal_args, *self._extra_args, **self._extra_kwargs)

    def __repr__(self) -> str:
        host = self._owner_ref()
        return f"<scoped {self._callback!r} owner={host!r}>"


class _WeakBoundCallable:
    """Closure-side replacement for a bound method whose host is the owner.

    Holds the function side strongly (it's just a function object — no
    cycle risk) and the host side weakly. At call time, dereferences
    the weakref and invokes ``func(host, *signal_args[:n])``. If the
    host is dead, the call is a no-op — the closure stays in place
    just long enough for the owner-weak-notify on the underlying
    GObject to fire and disconnect the handler at the GSignal layer.

    Substituted by `Signal.connect` only when the resolved owner *is*
    `callback.__self__`. For every other shape (lambdas, free
    functions, partials, bound methods where the host is not the
    owner) the regular adapter path runs unchanged.
    """

    __slots__ = ("_func", "_self_ref", "_n_args")

    def __init__(self, bound_method: types.MethodType, n_args: int | None) -> None:
        self._func = bound_method.__func__
        host = bound_method.__self__
        self._self_ref = weakref.ref(host)
        self._n_args = n_args

    def __call__(self, *signal_args: object) -> object:
        host = self._self_ref()
        if host is None:
            return None
        if self._n_args is None:
            return self._func(host, *signal_args)
        return self._func(host, *signal_args[: self._n_args])

    def __repr__(self) -> str:
        host = self._self_ref()
        func_name = (
            self._func.__qualname__
            if hasattr(self._func, "__qualname__")
            else repr(self._func)
        )
        return f"<weak-bound {func_name} on {host!r}>"
