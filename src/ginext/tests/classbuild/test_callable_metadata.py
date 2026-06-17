# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypeGuard


class _HasCallableMetadata(Protocol):
    __module__: str
    __doc__: str | None
    __defaults__: tuple[object, ...] | None
    __kwdefaults__: dict[str, object] | None
    __annotations__: dict[str, object]
    __annotate__: Callable[[], dict[str, object]]
    __type_params__: tuple[object, ...]
    __name__: str
    __qualname__: str


def _has_callable_metadata(method: object) -> TypeGuard[_HasCallableMetadata]:
    from ginext import GLib
    from ginext.method import GICallable

    return isinstance(method, (type(GLib.get_user_name), GICallable))


def test_imported_callables_expose_metadata() -> None:
    from ginext import GLib
    from ginext import Gio

    get_user_name = GLib.get_user_name
    cancel = Gio.Cancellable.cancel
    copy = Gio.File.copy

    assert _has_callable_metadata(get_user_name)
    assert _has_callable_metadata(cancel)
    assert _has_callable_metadata(copy)

    assert get_user_name.__module__ == "GLib"
    assert get_user_name.__doc__ is None
    assert get_user_name.__defaults__ is None
    assert get_user_name.__kwdefaults__ is None
    assert get_user_name.__annotations__ == {"return": str}
    assert get_user_name.__annotate__() == {"return": str}
    assert get_user_name.__type_params__ == ()

    assert cancel.__module__ == "Gio"
    assert cancel.__doc__ is None
    assert cancel.__defaults__ is None
    assert cancel.__kwdefaults__ is None
    assert cancel.__annotations__ == {"return": None}
    assert cancel.__annotate__() == {"return": None}
    assert cancel.__type_params__ == ()

    assert copy.__module__ == "Gio"
    assert copy.__doc__ is None
    assert copy.__defaults__ == (None, None)
    assert copy.__kwdefaults__ is None
    assert copy.__annotations__["destination"] is Gio.File
    assert copy.__annotations__["return"] is bool
    assert copy.__annotate__() == copy.__annotations__
    assert copy.__type_params__ == ()
