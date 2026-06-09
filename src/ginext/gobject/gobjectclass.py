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
    Self,
)

from .. import features
from .. import private
from ..signal.adapt import (
    _accepted_signal_arg_count,
)
from ..signal.bound import Signal as _SignalInstance
from ..signal.descriptor import SignalDescriptor as Signal
from .metaclass import GObjectMeta as GObjectMeta
from .resolve import classbuild_module, gobject_repo as gobject_repo
from .subclass import register_python_subclass
from .properties import (
    Property as Property,
    _PspecProperty,
    own_annotations_dict,
)

# GObject.Object is the C base type, built below by init_gobject from the method
# definitions in _GObjectBody. _GObjectBody subclasses the C type only for type
# checking (so its bodies and GObject see the full API); at runtime it is a bare
# namespace whose methods init_gobject installs on the C type.
if TYPE_CHECKING:
    _MethodsBase = private.GObject
else:
    _MethodsBase = object

_compat_dispose_state: dict[int, dict[str, object]] = {}
_G_TYPE_INTERFACE = 8


def _synthesize_pspec_property(cls: type, py_name: str) -> _PspecProperty:
    """Install (once) a descriptor for a GObject property the class didn't
    declare, so it reads/writes as a plain attribute. Also surface it in
    ``__annotations__`` so the class advertises the field, dataclass-style."""
    descriptor = _PspecProperty(py_name)
    setattr(cls, py_name, descriptor)
    annotations = own_annotations_dict(cls)
    if py_name not in annotations:
        cls.__annotations__ = {**annotations, py_name: object}
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


def _finish_construction(obj: "GObject", handlers: dict[str, object]) -> None:
    """Post-bind construction tail: run post-construct hooks, wire on_* handlers."""
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


# Runtime __setattr__/__getattr__ for GObject.Object, installed as overlays at
# creation (bottom of this module). Defined with non-dunder names so they are
# plain module functions (a module-level `def __getattr__` would become the
# module's PEP 562 attribute hook); registered under their dunder names.
def _obj_signal_for_name(self: Any, name: str) -> _SignalInstance:
    # Lazy signal lookup. Methods (and any other class attribute) are found via
    # normal __getattribute__ first; only true attribute misses fall here. Signal
    # names that collided with a method had the method rerouted into
    # signal_method_backings at class-build time, so asking for `obj.activate`
    # falls through here and produces a Signal with method backing.
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
        signal = cast("_SignalInstance", info.__get__(self, cls))
        if detail is not None:
            return signal.detail_signal(detail)
        return signal
    signal = _SignalInstance(self, gobject_name, info, cast("Any", method))
    if detail is not None:
        return signal.detail_signal(detail)
    return signal


def _obj_init_subclass(
    cls: type[GObject], /, type_name: str | None = None, **kwargs: object
) -> None:
    super(GObject, cls).__init_subclass__(**kwargs)
    register_python_subclass(cls, type_name=type_name)


def _obj_setattr(self: Any, name: str, value: object) -> None:
    # A write to an introspected/inherited GObject property must route through
    # the property system, not land in the instance dict: on first write to a
    # non-dunder name that names a pspec, synthesize the descriptor first.
    if not name.startswith("_"):
        cls = type(self)
        if not any(name in klass.__dict__ for klass in cls.__mro__):
            pspec = cls.gimeta.param_spec(name.replace("_", "-"))
            if pspec is not None:
                _synthesize_pspec_property(cls, name)
    object.__setattr__(self, name, value)


def _obj_getattr(self: Any, name: str) -> Any:
    if features.is_enabled(features.PYGOBJECT_COMPAT):
        dispose_state = _compat_dispose_state.get(id(self))
        if dispose_state is not None and name in dispose_state:
            return dispose_state[name]
    method = classbuild_module().method_for_instance(self, name)
    if method is not None:
        return method
    # Any GObject property is reachable as a plain attribute: on first miss,
    # synthesize a descriptor from its pspec and cache it on the class.
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

    if TYPE_CHECKING:
        # Runtime implementations are the _obj_* functions below (installed on
        # GObject.Object as overlays at creation) or the C tp_init; these stubs
        # keep the type-checking view complete — __getattr__ in particular is what
        # lets mypy allow dynamic property/signal attribute access, and __init__
        # types `GObject.Object(**properties)` / explicit base-init calls.
        def __init__(self, **properties: object) -> None: ...
        def __init_subclass__(
            cls, /, type_name: str | None = None, **kwargs: object
        ) -> None: ...
        def __setattr__(self, name: str, value: object) -> None: ...
        def __getattr__(self, name: str) -> Any: ...
        def signal_for_name(self, name: str) -> _SignalInstance: ...



if TYPE_CHECKING:
    GObject = _GObjectBody
else:
    GObject = private.init_gobject(GObjectMeta)
    private.GObject = GObject
    del _GObjectBody

GInterface.gimeta = private.GIMeta.from_type_name("GTypeInterface")
GObject.Signal = Signal
GObject.gimeta = private.GIMeta.from_type_name("GObject")

if not TYPE_CHECKING:
    # Hand every foundational instance hook to C at bootstrap. __getattr__ and
    # __setattr__ back the tp_getattro/tp_setattro slots and _finish_construction
    # backs tp_init; __init_subclass__ and signal_for_name are installed straight
    # onto the C type by register_gobject_callbacks. C never imports this module —
    # the dependency is one-directional — and there is no overlay round-trip.
    private.register_gobject_callbacks(
        getattr=_obj_getattr,
        setattr=_obj_setattr,
        finish_construction=_finish_construction,
        init_subclass=_obj_init_subclass,
        signal_for_name=_obj_signal_for_name,
    )
