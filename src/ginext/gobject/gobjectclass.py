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

"""ginext.GObject — the unified GObject base class.

One class for two construction paths:

- **Imported classes** (Gio.Cancellable, Gio.ListStore, etc.) — built by
  `ClassBuilder` via `type(name, bases, attrs)` with `gimeta` and the
  signal tables pre-populated in `attrs`. `__init_subclass__` detects
  this via `"gimeta" in cls.__dict__` and short-circuits the
  Python-defined-subclass registration.

- **Python-defined classes** — `class MyObj(GObject): ...`.
  `__init_subclass__` calls `GIMeta.register_subclass` to allocate a
  new GType, inherits the parent's signal tables, and registers any
  `GObject.Signal()` descriptors found in `cls.__dict__`.

Both paths share the same `__init__`, `__getattr__`, `scoped`, and
repr machinery — user-visible behaviour is identical regardless of
where the class came from.
"""

from __future__ import annotations

import sys
import difflib
from typing import (
    Any,
    Callable,
    ClassVar,
    dataclass_transform,
    cast,
    overload,
    Self,
)

from .. import features
from .. import private
from ..signal.adapt import (
    _SIGNAL_ARG_LIMIT_ATTR,
    _accepted_signal_arg_count,
    _split_constructor_kwargs,
)
from ..signal.bound import Signal as _SignalInstance
from ..signal.connection import SignalConnection
from ..signal.descriptor import SignalDescriptor as Signal
from ..signal.scoped import ScopedCallable, static_owner
from .metaclass import GObjectMeta as GObjectMeta
from .resolve import classbuild_module, gobject_repo as gobject_repo
from .subclass import register_python_subclass
from .properties import (
    Property as Property,
    _PspecProperty,
    call_notify_override,
)

_compat_aliases_enabled = False
_compat_dispose_state: dict[int, dict[str, object]] = {}
_G_TYPE_INTERFACE = 8


def signal_for_instance(obj: "GObject", name: str) -> _SignalInstance:
    return obj.signal_for_name(name)


def set_compat_aliases_enabled(enabled: bool) -> None:
    global _compat_aliases_enabled
    _compat_aliases_enabled = enabled


def _synthesize_pspec_property(cls: type, py_name: str) -> _PspecProperty:
    """Install (once) a descriptor for a GObject property the class didn't
    declare, so it reads/writes as a plain attribute. Also surface it in
    ``__annotations__`` so the class advertises the field, dataclass-style."""
    descriptor = _PspecProperty(py_name)
    setattr(cls, py_name, descriptor)
    annotations = cls.__dict__.get("__annotations__")
    if annotations is None:
        annotations = {}
        cls.__annotations__ = annotations
    annotations.setdefault(py_name, object)
    return descriptor


def _gimeta_extension_bucket(owner: object, namespace: str) -> dict[str, object] | None:
    try:
        gimeta = owner.gimeta  # type: ignore[attr-defined]
    except AttributeError:
        return None
    try:
        extensions = gimeta.extensions
    except AttributeError:
        return None
    if not isinstance(extensions, dict):
        return None
    bucket = extensions.get(namespace)
    if not isinstance(bucket, dict):
        return None
    return cast("dict[str, object]", bucket)


def _run_post_construct_hooks(obj: object) -> None:
    bucket = _gimeta_extension_bucket(type(obj), "core")
    hooks = bucket.get("post_construct_hooks", ()) if bucket is not None else ()
    if not isinstance(hooks, (list, tuple)):
        hooks = ()
    for hook in hooks:
        if not callable(hook):
            continue
        try:
            hook(obj)
        except (AttributeError, RuntimeError, TypeError) as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)


@overload
def _wrap_existing_pointer(
    cls: type["GObject"], ptr: int, *, run_post_construct: bool = True
) -> "GObject": ...


@overload
def _wrap_existing_pointer(
    cls: type["GInterface"], ptr: int, *, run_post_construct: bool = True
) -> "GInterface": ...


def _wrap_existing_pointer(
    cls: type[object],
    ptr: int,
    *,
    owns_ref: bool = True,
    run_post_construct: bool = True,
) -> object:
    if run_post_construct:
        return private.GObjectBase.from_c(ptr)
    bound_cls = cast("type[private.GObjectBase]", cls)
    obj = bound_cls.new_bound_from_c(ptr, owns_ref=owns_ref)
    if run_post_construct:
        _run_post_construct_hooks(obj)
    return obj


@overload
def wrap_existing_pointer_for_class(
    cls: type["GObject"], ptr: int, *, owns_ref: bool = True
) -> "GObject": ...


@overload
def wrap_existing_pointer_for_class(
    cls: type["GInterface"], ptr: int, *, owns_ref: bool = True
) -> "GInterface": ...


def wrap_existing_pointer_for_class(
    cls: type[object], ptr: int, *, owns_ref: bool = True
) -> object:
    bound_cls = cast("type[private.GObjectBase]", cls)
    obj = bound_cls.new_bound_from_c(ptr, owns_ref=owns_ref)
    _run_post_construct_hooks(obj)
    return obj


def _prime_preallocated_construction(
    obj: "GObject", ptr: int, handlers: dict[str, object] | None = None
) -> None:
    obj.prime_construction_state(ptr, handlers)


def _wrap_preallocated_construction(
    cls: type["GObject"], ptr: int, handlers: dict[str, object] | None = None
) -> "GObject":
    return cls.new_preallocated_from_c(ptr, handlers)


def _consume_preallocated_construction(
    obj: "GObject",
) -> tuple[int, dict[str, object]] | None:
    state = obj.take_construction_state()
    if state is None:
        return None
    return state


def _is_python_defined_gobject_subclass(type_or_gtype: object) -> bool:
    if not isinstance(type_or_gtype, type):
        return False
    if not issubclass(type_or_gtype, GObject):
        return False
    try:
        gimeta = type_or_gtype.gimeta
    except AttributeError:
        return False
    try:
        gi_info = gimeta.gi_info
    except AttributeError:
        return False
    return gi_info is None


def _split_gobject_constructor_kwargs(
    kwargs: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    if features.is_enabled(features.NEW_SIGNAL_API):
        return _split_constructor_kwargs(kwargs)
    return dict(kwargs), {}


def _normalize_constructor_properties(
    properties: dict[str, object],
) -> dict[str, object]:
    if properties and not features.is_enabled(features.GOBJECT_PROPERTY_CONSTRUCTOR):
        names = ", ".join(sorted(properties))
        raise TypeError(f"GObject property constructor kwargs are disabled: {names}")
    return {name.replace("_", "-"): value for name, value in properties.items()}


def _finish_wrapper_construction(
    obj: "GObject", ptr: int, handlers: dict[str, object], *, owns_ref: bool
) -> None:
    obj.bind_from_c(ptr, owns_ref=owns_ref)
    _run_post_construct_hooks(obj)
    for signal_attr_name, callback in handlers.items():
        if not callable(callback):
            raise TypeError(
                f"on_{signal_attr_name}= must be callable, got {type(callback).__name__}"
            )
        signal_infos = type(obj).gimeta.signal_infos
        if signal_attr_name not in signal_infos:
            available = sorted(signal_infos)
            close = difflib.get_close_matches(signal_attr_name, available, n=3)
            hint = f"; did you mean {close!r}?" if close else ""
            raise TypeError(
                f"{type(obj).__name__} has no signal named "
                f"{signal_attr_name!r} (from on_{signal_attr_name}=){hint}"
            )
        arg_limit = _accepted_signal_arg_count(cast("Callable[..., Any]", callback))
        obj.connect_constructor_handler(
            signal_attr_name,
            callback,
            -1 if arg_limit is None else int(arg_limit),
        )


def _push_python_construction() -> None:
    private.GObjectBase.push_python_construction()


def _pop_python_construction() -> None:
    private.GObjectBase.pop_python_construction()


def _python_construction_active() -> bool:
    return bool(private.GObjectBase.python_construction_active())


@dataclass_transform(field_specifiers=(Property,))
class GInterface(private.GObjectBase, metaclass=GObjectMeta):
    gimeta: ClassVar[private.GIMeta]
    _class_struct_name: ClassVar[str | None] = None
    __slots__ = ()

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        if (
            int(gobject_repo().type_fundamental(int(cls.gimeta.gtype)))
            != _G_TYPE_INTERFACE
        ):
            return private.GObjectBase.__new__(cls)
        raise NotImplementedError(
            f"{cls.__module__}.{cls.__name__} is an interface and cannot be instantiated"
        )


@dataclass_transform(field_specifiers=(Property,))
class GObject(private.GObjectBase, metaclass=GObjectMeta):
    gimeta: ClassVar[private.GIMeta]
    Signal: ClassVar[type[Signal]]
    _class_struct_name: ClassVar[str | None] = None

    # Class-level signal lookup table: normalized python name → GISignalInfo
    # (or SignalDescriptor for Python-defined signals). Inherited from the
    # parent class at class-build time; the explicit copy is necessary
    # because plain MRO attribute lookup would expose only the closest
    # class's dict, not a merged view across the chain.
    # Stored on gimeta (signal_infos, signal_method_backings, vfunc_infos).

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        return private.GObjectBase.__new__(cls)

    def __init_subclass__(
        cls, /, type_name: str | None = None, **kwargs: object
    ) -> None:
        super().__init_subclass__(**kwargs)
        register_python_subclass(cls, type_name=type_name)

    def __init__(self, **kwargs: object) -> None:
        properties, handlers = _split_gobject_constructor_kwargs(kwargs)
        normalized = _normalize_constructor_properties(properties)
        state = _consume_preallocated_construction(self)
        if state is None:
            _push_python_construction()
            try:
                ptr = type(self).construct_with_properties(normalized)
            finally:
                _pop_python_construction()
            _finish_wrapper_construction(self, ptr, handlers, owns_ref=True)
            return
        ptr, pending_handlers = state
        if normalized:
            self.apply_construction_properties(normalized)
        merged_handlers = dict(pending_handlers)
        merged_handlers.update(handlers)
        _finish_wrapper_construction(self, ptr, merged_handlers, owns_ref=False)

    @classmethod
    def _from_gobject_pointer(cls, ptr: int) -> "GObject":
        return wrap_existing_pointer_for_class(cls, ptr)

    def __del__(self) -> None:
        if not self.is_bound():
            return
        owns_ref = self.owns_ref()
        if not owns_ref:
            return
        self.preserve_wrapper_state()
        if features.is_enabled(
            features.PYGOBJECT_COMPAT
        ) and _is_python_defined_gobject_subclass(type(self)):
            has_python_dispose = False
            for cls in type(self).__mro__:
                if not issubclass(cls, GObject):
                    continue
                if cls is GObject:
                    break
                if not _is_python_defined_gobject_subclass(cls):
                    continue
                if "do_dispose" in cls.__dict__:
                    has_python_dispose = True
                    break
            if not has_python_dispose:
                self.release_ref()
                return
            dispose_state = dict(vars(self))
            if dispose_state:
                _compat_dispose_state[id(self)] = dispose_state
            try:
                self.bind_from_c(self)
                super().run_dispose()
            except AttributeError, RuntimeError, TypeError, ValueError:
                pass
            finally:
                _compat_dispose_state.pop(id(self), None)
        # Raw C unref, not the introspected GObject.Object.unref: __del__ runs
        # during interpreter shutdown when sys.meta_path is gone, so a lazy
        # `from ginext import GObject` would ImportError and leak the ref.
        self.release_ref()

    def scoped(
        self, callback: Callable[..., Any], *args: object, **kwargs: object
    ) -> ScopedCallable:
        """Wrap a callback so its owner is this instance.

        Use with lambdas / free functions / nested functions / partials
        where `owner=self` would otherwise be needed. The wrapper's
        `__self__` is this instance, so `Signal.connect`'s inference
        path picks it up automatically. Extra args/kwargs are appended
        after the runtime signal args:

            button.clicked.connect(self.scoped(self.run_action, "save"))
        """
        return ScopedCallable(self, callback, *args, **kwargs)

    def connect(
        self,
        signal_name: str,
        callback: Callable[..., Any],
        *user_data: object,
        **kwargs: object,
    ) -> SignalConnection:
        if not features.is_enabled(features.OLD_SIGNAL_API):
            raise TypeError("GObject.connect() is disabled by old_signal_api")
        if user_data:
            original_callback = callback
            signal_arg_limit = _accepted_signal_arg_count(
                original_callback, len(user_data)
            )

            def callback(*signal_args: object) -> object:
                return original_callback(*signal_args, *user_data)

            setattr(callback, _SIGNAL_ARG_LIMIT_ATTR, signal_arg_limit)
            kwargs.setdefault("owner", static_owner)
        signal = self.signal_for_name(signal_name)
        kwargs.setdefault("_weak_callback_record", True)
        connection = signal.connect(callback, **cast("Any", kwargs))
        self._compat_remember_connection(connection)
        return connection

    def connect_after(
        self,
        signal_name: str,
        callback: Callable[..., Any],
        *user_data: object,
        **kwargs: object,
    ) -> SignalConnection:
        kwargs["after"] = True
        return self.connect(signal_name, callback, *user_data, **kwargs)

    def emit(self, signal_name: str, *args: object) -> object:
        if not features.is_enabled(features.OLD_SIGNAL_API):
            raise TypeError("GObject.emit() is disabled by old_signal_api")
        signal = self._compat_signal_for_name(signal_name)
        return signal.emit(*args)

    def get_property(self, name: str) -> object:
        prop_name = name.replace("_", "-")
        try:
            return type(self).gimeta.get_property(self, prop_name)
        except AttributeError:
            return self.get_property_by_name(prop_name)

    def set_property(self, name: str, value: object) -> None:
        prop_name = name.replace("_", "-")
        try:
            type(self).gimeta.set_property(self, prop_name, value)
        except AttributeError:
            self.set_property_by_name(prop_name, value)
        call_notify_override(self, prop_name)

    def disconnect(self, connection: SignalConnection | int) -> None:
        if isinstance(connection, SignalConnection):
            connection.disconnect()
            self._compat_forget_connection(connection)
            return
        if not features.is_enabled(features.OLD_SIGNAL_API):
            raise TypeError(
                "GObject.disconnect(handler_id) is disabled by old_signal_api"
            )
        self.disconnect_handler_id(int(connection))
        self._compat_forget_handler_id(int(connection))

    def handler_is_connected(self, handler_id: object) -> bool:
        raw = (
            handler_id.handler_id
            if isinstance(handler_id, SignalConnection)
            else handler_id
        )
        return bool(self.handler_id_is_connected(int(cast("Any", raw))))

    def stop_emission_by_name(self, detailed_signal: str) -> None:
        super().stop_emission_by_name(detailed_signal)

    def freeze_notify(self) -> None:
        super().freeze_notify()

    def thaw_notify(self) -> None:
        super().thaw_notify()

    def run_dispose(self) -> None:
        super().run_dispose()

    def _is_floating_for_test(self) -> bool:
        return bool(self.is_floating())

    def _force_floating(self) -> None:
        self.make_floating()

    def _ref_sink(self) -> None:
        self.ref_sink()

    def _compat_connections(self) -> list[SignalConnection]:
        connections = vars(self).get("_compat_signal_connections")
        if connections is None:
            connections = []
            self._compat_signal_connections = connections
        return cast("list[SignalConnection]", connections)

    def _compat_remember_connection(self, connection: SignalConnection) -> None:
        self._compat_connections().append(connection)

    def _compat_forget_connection(self, connection: SignalConnection) -> None:
        connections = self._compat_connections()
        if connection in connections:
            connections.remove(connection)

    def _compat_forget_handler_id(self, handler_id: int) -> None:
        connections = self._compat_connections()
        connections[:] = [c for c in connections if c.handler_id != handler_id]

    @property
    def __grefcount__(self) -> int:
        return self.ref_count()

    def _compat_property_for_name(self, name: str) -> object:
        prop_name = name.replace("_", "-").removesuffix("-")
        try:
            return type(self).gimeta.get_property(self, prop_name)
        except AttributeError:
            try:
                return self.get_property_by_name(prop_name)
            except AttributeError, TypeError:
                raise AttributeError(name) from None

    def __setattr__(self, name: str, value: object) -> None:
        # Writes to an introspected/inherited GObject property must route through
        # the property system, not land in the instance dict. Mirror __getattr__:
        # on first write to a name that isn't already a class attribute but does
        # name a pspec, synthesize the descriptor, then let it handle the set.
        # Property names never start with "_", so internal sets skip the lookup.
        if not name.startswith("_"):
            cls = type(self)
            if not any(name in klass.__dict__ for klass in cls.__mro__):
                pspec = cls.gimeta.param_spec(name.replace("_", "-"))
                if pspec is not None:
                    _synthesize_pspec_property(cls, name)
        object.__setattr__(self, name, value)

    def __getattr__(self, name: str) -> Any:
        if features.is_enabled(features.PYGOBJECT_COMPAT):
            dispose_state = _compat_dispose_state.get(id(self))
            if dispose_state is not None and name in dispose_state:
                return dispose_state[name]
        method = classbuild_module().method_for_instance(self, name)
        if method is not None:
            return method
        # Any GObject property (introspected or inherited) is reachable as a
        # plain attribute: on first miss, synthesize a descriptor from its pspec
        # and cache it on the class. Property names never start with "_", so
        # dunder/private misses skip the (C) pspec lookup.
        if not name.startswith("_"):
            cls = type(self)
            pspec = cls.gimeta.param_spec(name.replace("_", "-"))
            if pspec is not None:
                return _synthesize_pspec_property(cls, name).__get__(self, cls)
        if features.is_enabled(features.PYGOBJECT_COMPAT):
            if name == "__gtype__":
                return type(self).__gtype__
            try:
                return self._compat_property_for_name(name)
            except AttributeError:
                pass
        if name.replace("-", "_") in type(self).gimeta.signal_infos:
            if not features.is_enabled(features.NEW_SIGNAL_API):
                raise AttributeError(name)
            return self.signal_for_name(name)
        if not features.is_enabled(features.NEW_SIGNAL_API):
            raise AttributeError(name)
        return self.signal_for_name(name)

    def signal_for_name(self, name: str) -> _SignalInstance:
        # Lazy signal lookup. Methods (and any other class attribute) are
        # found via normal __getattribute__ first; only true attribute misses
        # fall here. Signal names that collided with a method had the method
        # rerouted into `_signal_method_backings` at class-build time, so
        # asking for `obj.activate` falls through to this branch and produces
        # a Signal with method backing.
        if not isinstance(name, str):
            raise TypeError(f"signal name must be a str, not {type(name).__name__}")
        if "::" in name:
            name, detail = name.split("::", 1)
        else:
            detail = None
        name = name.replace("-", "_")
        cls = type(self)
        info = cls.gimeta.signal_infos.get(name)
        method = cls.gimeta.signal_method_backings.get(name)
        if info is None and cls is GObject:
            obj_cls = gobject_repo().Object
            info = obj_cls.gimeta.signal_infos.get(name)
            method = obj_cls.gimeta.signal_method_backings.get(name)
        if info is None:
            raise AttributeError(name)
        gobject_name = name.replace("_", "-")
        if isinstance(info, Signal):
            signal = info.__get__(self, cls)
            if detail is not None:
                return signal.detail_signal(detail)
            return signal
        signal = _SignalInstance(self, gobject_name, info, cast("Any", method))
        if detail is not None:
            return signal.detail_signal(detail)
        return signal

    def _compat_signal_for_name(self, name: str) -> _SignalInstance:
        try:
            return self.signal_for_name(name)
        except AttributeError:
            return _SignalInstance(self, name.replace("_", "-"), None, None)

    def __repr__(self) -> str:
        module = (
            type(self).__module__.removeprefix("ginext.").removeprefix("gi.repository.")
        )
        type_name = type(self).gimeta.type_name
        if not self.is_bound():
            return (
                f"<{module}.{type(self).__name__} object at 0x{id(self):x} "
                f"({type_name} unbound)>"
            )
        if features.is_enabled(features.PYGOBJECT_COMPAT):
            return (
                f"<{module}.{type(self).__name__} object at 0x{id(self):x} "
                f"({type_name} at 0x{id(self):x})>"
            )
        return (
            f"<{module}.{type(self).__name__} object at 0x{id(self):x} ({type_name})>"
        )


GInterface.gimeta = private.GIMeta.from_type_name("GTypeInterface")
GObject.Signal = Signal
# __init_subclass__ only fires for subclasses, so the root must be wired up
# explicitly. GLib's type lookup works without an explicit g_type_init() in
# modern GLib — the type system auto-initializes on first use.
GObject.gimeta = private.GIMeta.from_type_name("GObject")

for _name in (
    "_from_gobject_pointer",
    "__del__",
    "scoped",
    "connect",
    "connect_after",
    "emit",
    "get_property",
    "set_property",
    "disconnect",
    "handler_is_connected",
    "stop_emission_by_name",
    "freeze_notify",
    "thaw_notify",
    "run_dispose",
    "_is_floating_for_test",
    "_force_floating",
    "_ref_sink",
    "_compat_connections",
    "_compat_remember_connection",
    "_compat_forget_connection",
    "_compat_forget_handler_id",
    "_compat_property_for_name",
    "__setattr__",
    "__getattr__",
    "signal_for_name",
    "_compat_signal_for_name",
    "__repr__",
    "__grefcount__",
):
    setattr(GInterface, _name, GObject.__dict__[_name])
