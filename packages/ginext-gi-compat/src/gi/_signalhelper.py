# Copyright 2026 Johan Dahlin
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

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, cast

from . import _gi
from ginext.signal.descriptor import SignalDescriptor

if TYPE_CHECKING:
    from collections.abc import Sequence


class Signal(str):
    class BoundSignal(str):
        def __new__(cls, signal: "Signal", gobj: object):
            return str.__new__(cls, str(signal))

        def __init__(self, signal: "Signal", gobj: Any) -> None:
            self.signal = signal
            self.gobj = gobj

        def __repr__(self) -> str:
            return f'BoundSignal("{self}")'

        def __call__(self, *args: object, **kwargs: object) -> object:
            if self.signal.func is None:
                raise TypeError(f"{self!s} has no default handler")
            return self.signal.func(self.gobj, *args, **kwargs)

        def connect(self, callback: object, *args: object, **kwargs: object) -> object:
            return self.gobj.connect(str(self), callback, *args, **kwargs)

        def connect_detailed(
            self, callback: object, detail: str, *args: object, **kwargs: object
        ) -> object:
            return self.gobj.connect(f"{self}::{detail}", callback, *args, **kwargs)

        def disconnect(self, handler_id: object) -> None:
            self.gobj.disconnect(handler_id)

        def emit(self, *args: object, **kwargs: object) -> object:
            return self.gobj.emit(str(self), *args, **kwargs)

    def __new__(cls, name: object = "", *args: object, **kwargs: object):
        if callable(name):
            name = getattr(name, "__name__", str(name))
        return str.__new__(cls, str(name))

    def __init__(
        self,
        name: object = "",
        func: Callable[..., Any] | None = None,
        flags: object = _gi.SIGNAL_RUN_FIRST,
        return_type: object = None,
        arg_types: "Sequence[object] | None" = None,
        doc: str = "",
        accumulator: object = None,
        accu_data: object = None,
    ) -> None:
        if func is None and callable(name):
            func = cast("Callable[..., Any]", name)
        if func is not None and not doc:
            doc = getattr(func, "__doc__", "") or ""
        if func is not None and not (return_type or arg_types):
            return_type, arg_types = get_signal_annotations(func)
        if arg_types is None:
            arg_types = ()

        self.func = func
        self.flags = flags
        self.return_type = return_type
        self.arg_types = arg_types
        self.__doc__ = doc
        self.accumulator = accumulator
        self.accu_data = accu_data

    def __get__(self, instance: object, owner: type | None = None) -> object:
        if instance is None:
            return self
        return self.BoundSignal(self, instance)

    def __call__(self, obj: object, *args: object, **kwargs: object) -> object:
        if isinstance(obj, _gi.GObject):
            if self.func is None:
                raise TypeError(f"{self!s} has no default handler")
            return self.func(obj, *args, **kwargs)

        name = str(self) if str(self) else getattr(obj, "__name__", "")
        return type(self)(
            name=name,
            func=cast("Callable[..., Any]", obj),
            flags=self.flags,
            return_type=self.return_type,
            arg_types=self.arg_types,
            doc=self.__doc__ or "",
            accumulator=self.accumulator,
            accu_data=self.accu_data,
        )

    def copy(self, new_name: str | None = None) -> "Signal":
        return type(self)(
            name=new_name or str(self),
            func=self.func,
            flags=self.flags,
            return_type=self.return_type,
            arg_types=self.arg_types,
            doc=self.__doc__ or "",
            accumulator=self.accumulator,
            accu_data=self.accu_data,
        )

    def get_signal_args(self) -> tuple[object, object, object, object, object] | str:
        return (
            self.flags,
            self.return_type,
            self.arg_types,
            self.accumulator,
            self.accu_data,
        )


class SignalOverride(Signal):
    def get_signal_args(self) -> str:
        return "override"


def get_signal_annotations(func: object) -> tuple[object, tuple[object, ...]]:
    annotations = getattr(func, "__annotations__", None)
    if not annotations:
        return None, ()

    callable_func = cast("Callable[..., object]", func)
    evaluated = inspect.get_annotations(callable_func, eval_str=True)
    spec = inspect.getfullargspec(callable_func)
    arg_types = tuple(evaluated[name] for name in spec.args if name in evaluated)
    return evaluated.get("return"), arg_types


def install_signals(cls: type) -> None:
    gsignals = cls.__dict__.get("__gsignals__", {})
    if not isinstance(gsignals, dict):
        raise TypeError(f"__gsignals__ must be a dict, not {type(gsignals).__name__!r}")

    newsignals = {}
    for name, signal in cls.__dict__.items():
        if not isinstance(signal, Signal):
            continue
        signal_name = str(signal)
        if not signal_name:
            signal_name = name
            signal = signal.copy(name)
            setattr(cls, name, signal)
        if signal_name in gsignals:
            raise ValueError(f'Signal "{name}" has already been registered.')
        newsignals[signal_name] = signal
        gsignals[signal_name] = signal.get_signal_args()

    _cls: Any = cls
    _cls.__gsignals__ = gsignals

    for name, signal in newsignals.items():
        if signal.func is None:
            continue
        func_name = "do_" + name.replace("-", "_")
        # A user-written do_<name> wins, but the native vfunc chain-up wrapper
        # inherited from GObject.Object must not block the override from being
        # installed as the default handler.
        existing = getattr(cls, func_name, None)
        if existing is None or type(existing).__name__ == "VFuncWrapper":
            setattr(cls, func_name, signal.func)


class _CompatSignalDescriptor(SignalDescriptor):
    def __init__(
        self,
        *arg_types: type,
        name: str | None = None,
        return_type: type | None = None,
        flags: int = 0,
        accumulator: object = None,
        accu_data: object = None,
    ) -> None:
        super().__init__(*arg_types, name=name, return_type=return_type)
        self._flags = flags
        self._compat_flags = flags
        self._compat_return_type = return_type
        self._accumulator = accumulator
        self._accu_data = accu_data

    def _extra_register_args(self) -> tuple[object, ...]:
        return (self._flags, self._accumulator, self._accu_data)


def _compat_signal_type(value_type: object) -> object:
    from ginext.gobject.gtype import GType

    if value_type is object:
        return GType.POINTER
    return value_type


def iter_pygobject_signal_descriptors(
    cls: type,
) -> list[tuple[str, SignalDescriptor]]:
    from ginext.gobject.resolve import own_gimeta

    _missing = object()
    gsignals = cls.__dict__.get("__gsignals__", _missing)
    if gsignals is _missing:
        return []
    if not isinstance(gsignals, dict):
        raise TypeError(f"__gsignals__ must be a dict, not {type(gsignals).__name__!r}")
    if not gsignals:
        return []

    result: list[tuple[str, SignalDescriptor]] = []
    for raw_name, spec in gsignals.items():
        if not isinstance(raw_name, str):
            raise TypeError("__gsignals__ names must be strings")
        if spec == "override":
            overrides = set(cls.__dict__.get("_pygobject_signal_overrides", set()))
            overrides.add(raw_name.replace("_", "-"))
            cls._pygobject_signal_overrides = overrides  # type: ignore[attr-defined]
            attr_name = raw_name.replace("-", "_")
            gimeta = own_gimeta(cls)
            if gimeta is None or attr_name not in gimeta.signal_infos:
                raise TypeError(f"cannot override unknown signal {raw_name!r}")
            continue
        if not isinstance(spec, tuple | list) or len(spec) not in (3, 5):
            raise TypeError(f"invalid signal specification for {raw_name!r}")
        flags, return_type, arg_types = spec[:3]
        accumulator = spec[3] if len(spec) == 5 else None
        accu_data = spec[4] if len(spec) == 5 else None
        if arg_types is None:
            arg_types = ()
        if not isinstance(arg_types, tuple | list):
            raise TypeError(f"invalid signal argument specification for {raw_name!r}")
        attr_name = raw_name.replace("-", "_")
        signal_name = raw_name.replace("_", "-")
        resolved_arg_types = tuple(_compat_signal_type(t) for t in arg_types)
        resolved_return_type = _compat_signal_type(return_type)
        descriptor = _CompatSignalDescriptor(
            *cast("tuple[type, ...]", resolved_arg_types),
            name=signal_name,
            return_type=cast("type | None", resolved_return_type),
            flags=int(cast("Any", flags)),
            accumulator=accumulator,
            accu_data=accu_data,
        )
        descriptor.__set_name__(cls, attr_name)
        result.append((attr_name, descriptor))
    return result
