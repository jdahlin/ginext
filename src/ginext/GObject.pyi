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

from __future__ import annotations

from typing import (
    Any,
    Callable,
    ClassVar,
    Final,
    Generic,
    Literal,
    ParamSpec as _ParamSpec,
    Self,
    TypeVar,
    overload,
)

from gi.repository import GObject as _CompatGObject  # type: ignore[import-untyped]
from ginext.private import GIMeta as _GIMeta

from .signal.connection import SignalConnection as SignalConnection

_SigO = TypeVar("_SigO")
_SigP = _ParamSpec("_SigP")
_SigR = TypeVar("_SigR")

Binding = _CompatGObject.Binding
ParamSpec = _CompatGObject.ParamSpec
Property = _CompatGObject.Property
SignalFlags = _CompatGObject.SignalFlags
ParamFlags = _CompatGObject.ParamFlags

class _Signal(Generic[_SigO, _SigP, _SigR]):
    def __call__(self, *args: _SigP.args, **kwargs: _SigP.kwargs) -> _SigR: ...
    def connect(
        self,
        handler: Callable[..., object],
        *,
        after: bool = ...,
        once: bool = ...,
        owner: Any = ...,
    ) -> SignalConnection: ...
    def connect_after(
        self,
        handler: Callable[..., object],
    ) -> SignalConnection: ...
    def emit(self, *args: _SigP.args, **kwargs: _SigP.kwargs) -> _SigR: ...
    def disconnect(self, connection: SignalConnection) -> None: ...
class _DetailedSignal(_Signal[_SigO, _SigP, _SigR]):
    @overload
    def __call__(self, detail: str | Any) -> "_Signal[_SigO, _SigP, _SigR]": ...
    @overload
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

Signal = _Signal
SignalMethod = _Signal
DetailedSignal = _DetailedSignal

class _HandlerBlockContext:
    def __init__(self, obj: Object, handler_id: int) -> None: ...
    def __enter__(self) -> _HandlerBlockContext: ...
    def __exit__(
        self, exc_type: object, exc_value: object, tb: object
    ) -> Literal[False]: ...

class _FreezeNotifyContext:
    def __init__(self, obj: object) -> None: ...
    def __enter__(self) -> _FreezeNotifyContext: ...
    def __exit__(
        self, exc_type: object, exc_value: object, tb: object
    ) -> Literal[False]: ...

class GEnum(int):
    """Base class for Python-defined GObject enum types (pending implementation)."""

    __gtype__: ClassVar[Any]

class GFlags(int):
    """Base class for Python-defined GObject flags types (pending implementation)."""

    __gtype__: ClassVar[Any]

class Object(_CompatGObject.Object):  # type: ignore[misc]
    gimeta: ClassVar[_GIMeta]
    def __init_subclass__(cls, *, type_name: str = ..., **kwargs: object) -> None: ...
    __gtype_name__: Final[str]
    notify: "DetailedSignal[Self, Any, None]"  # type: ignore[assignment]
    def freeze_notify(self) -> "_FreezeNotifyContext": ...  # type: ignore[override]
    def handler_block(  # type: ignore[override]
        self, handler_id: int | SignalConnection
    ) -> _HandlerBlockContext: ...
    def handler_unblock(self, handler_id: int | SignalConnection) -> None: ...

def __getattr__(name: str) -> Any: ...
