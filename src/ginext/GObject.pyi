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

from gi.repository import GObject as _CompatGObject
from ginext.private import GIMeta

from .signal.connection import SignalConnection as SignalConnection

SigO = TypeVar("SigO")
_SigP = _ParamSpec("_SigP")
SigR = TypeVar("SigR")

# These are re-exported from gi.repository.GObject; callers use the generated
# stubs in build/stubs/ginext/GObject.pyi for precise types.
Binding: Any = ...
ParamSpec: Any = ...
Property: Any = ...
SignalFlags: Any = ...
ParamFlags: Any = ...


class Signal(Generic[SigO, _SigP, SigR]):
    def __call__(self, *args: _SigP.args, **kwargs: _SigP.kwargs) -> SigR: ...
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
    def emit(self, *args: _SigP.args, **kwargs: _SigP.kwargs) -> SigR: ...
    def disconnect(self, connection: SignalConnection) -> None: ...
class DetailedSignal(Signal[SigO, _SigP, SigR]):
    @overload
    def __call__(self, detail: str | Any) -> "Signal[SigO, _SigP, SigR]": ...
    @overload
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

Signal = Signal
SignalMethod = Signal
DetailedSignal = DetailedSignal

class HandlerBlockContext:
    def __init__(self, obj: Object, handler_id: int) -> None: ...
    def __enter__(self) -> HandlerBlockContext: ...
    def __exit__(
        self, exc_type: object, exc_value: object, tb: object
    ) -> Literal[False]: ...

class FreezeNotifyContext:
    def __init__(self, obj: object) -> None: ...
    def __enter__(self) -> FreezeNotifyContext: ...
    def __exit__(
        self, exc_type: object, exc_value: object, tb: object
    ) -> Literal[False]: ...

class GEnum(int):
    """Base class for Python-defined GObject enum types (pending implementation)."""

    __gtype__: ClassVar[Any]

class GFlags(int):
    """Base class for Python-defined GObject flags types (pending implementation)."""

    __gtype__: ClassVar[Any]

class Object(_CompatGObject.Object):  # type: ignore[misc, name-defined]
    gimeta: ClassVar[GIMeta]
    def __init_subclass__(cls, *, type_name: str = ..., **kwargs: object) -> None: ...
    __gtype_name__: Final[str]
    notify: "DetailedSignal[Self, Any, None]"
    def freeze_notify(self) -> "FreezeNotifyContext": ...
    def handler_block(
        self, handler_id: int | SignalConnection
    ) -> HandlerBlockContext: ...
    def handler_unblock(self, handler_id: int | SignalConnection) -> None: ...

def __getattr__(name: str) -> Any: ...
