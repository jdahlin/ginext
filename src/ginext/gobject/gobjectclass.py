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
    TYPE_CHECKING,
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
    _accepted_signal_arg_count,
    _split_constructor_kwargs,
)
from ..signal.bound import Signal as _SignalInstance
from ..signal.descriptor import SignalDescriptor as Signal
from ..signal.scoped import ScopedCallable
from .metaclass import GObjectMeta as GObjectMeta
from .resolve import classbuild_module, gobject_repo as gobject_repo
from .subclass import register_python_subclass
from .properties import (
    Property as Property,
    _PspecProperty,
)

# GObject.Object is the C base type, built below by init_gobject from the method
# definitions in _GObjectBody. _GObjectBody subclasses the C type only for type
# checking (so its bodies and GObject see the full API); at runtime it is a bare
# namespace whose methods init_gobject installs on the C type.
if TYPE_CHECKING:
    _MethodsBase = private.GObject
else:
    _MethodsBase = object

_compat_aliases_enabled = False
_compat_dispose_state: dict[int, dict[str, object]] = {}
_G_TYPE_INTERFACE = 8


def _compat_finalize_dispose(self: "GObject") -> None:
    # pygobject compat: run a Python `do_dispose` override during finalization,
    # while the wrapper's instance dict is still reachable (stashed in
    # _compat_dispose_state so __getattr__ can serve it mid-dispose). Caller has
    # already checked PYGOBJECT_COMPAT and that self is a python-defined subclass.
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
        return
    dispose_state = dict(vars(self))
    if dispose_state:
        _compat_dispose_state[id(self)] = dispose_state
    try:
        self.bind_from_c(self)
        _base_run_dispose(self)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    finally:
        _compat_dispose_state.pop(id(self), None)


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
        return private.GObject.from_c(ptr)
    bound_cls = cast("type[private.GObject]", cls)
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
    bound_cls = cast("type[private.GObject]", cls)
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


# A layout-free mixin sibling of GObject.Object, so `class Foo(GObject.Object,
# SomeInterface)` has a consistent MRO. Never instantiated as itself.
@dataclass_transform(field_specifiers=(Property,))
class GInterface(metaclass=GObjectMeta):
    gimeta: ClassVar[private.GIMeta]
    _class_struct_name: ClassVar[str | None] = None
    __slots__ = ()

    def __new__(cls, *args: object, **kwargs: object) -> Self:
        if (
            int(gobject_repo().type_fundamental(int(cls.gimeta.gtype)))
            != _G_TYPE_INTERFACE
        ):
            return GObject.__new__(cls)
        raise NotImplementedError(
            f"{cls.__module__}.{cls.__name__} is an interface and cannot be instantiated"
        )


# The GObject.Object method definitions. init_gobject installs these on the C
# type; _GObjectBody itself is only the type-checking view of GObject.
@dataclass_transform(field_specifiers=(Property,))
class _GObjectBody(_MethodsBase, metaclass=GObjectMeta):
    gimeta: ClassVar[private.GIMeta]
    Signal: ClassVar[type[Signal]]
    _class_struct_name: ClassVar[str | None] = None
    _gobject_is_root: ClassVar[bool] = True
    _gobject_root_adopted: ClassVar[bool]

    def __init_subclass__(
        cls, /, type_name: str | None = None, **kwargs: object
    ) -> None:
        super(GObject, cls).__init_subclass__(**kwargs)
        register_python_subclass(cls, type_name=type_name)

    def __init__(self, **kwargs: object) -> None:
        properties, handlers = _split_gobject_constructor_kwargs(kwargs)
        normalized = _normalize_constructor_properties(properties)
        state = _consume_preallocated_construction(self)
        if state is None:
            ptr = type(self).construct_with_properties(normalized)
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



if TYPE_CHECKING:
    GObject = _GObjectBody
else:
    GObject = private.init_gobject(GObjectMeta, _GObjectBody)
    private.GObject = GObject
    del _GObjectBody

_base_run_dispose = GObject.run_dispose
GInterface.gimeta = private.GIMeta.from_type_name("GTypeInterface")
GObject.Signal = Signal
GObject.gimeta = private.GIMeta.from_type_name("GObject")
