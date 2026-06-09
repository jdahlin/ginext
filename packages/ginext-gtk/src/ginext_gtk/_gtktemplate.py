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

import os
import threading
from collections import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast, dataclass_transform
from xml.etree import ElementTree

from ginext import GLib, Gio

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    # The `ginext` namespaces (Gtk, ...) are dynamic `Namespace` values whose
    # attribute access resolves to Any at runtime, so their types cannot be used
    # as static type symbols here. The typed surface ships as the separate
    # ginext-stubs package and cannot be wired in-repo. Alias the types we
    # annotate with to Any so mypy can resolve the names.
    Gtk = Any

    class _TemplateWidgetType(type[Any]):
        def init_template(self, *args: object, **kwargs: object) -> object: ...
        def set_template(self, template: object) -> None: ...


TemplateValidation = Literal["strict", "warn", "ignore"]
TemplateSourceKind = Literal["string", "filename", "resource_path"]
# Bound to Gtk.Widget at runtime; Gtk is a dynamic Namespace (see alias above),
# so the static bound is Any.
WidgetT = TypeVar("WidgetT", bound=Any)

_TEMPLATE_RUNTIME_KEY = "template"
_POST_CONSTRUCT_HOOKS_KEY = "post_construct_hooks"
_INITIALIZED_ATTR = "_gtk_template_initialized"
_builder_scope_cls: type[object] | None = None
_active_template_instance = threading.local()
_CONNECT_SWAPPED = 2


@dataclass(slots=True, frozen=True)
class TemplateSource:
    kind: TemplateSourceKind
    value: str | bytes


@dataclass(slots=True, frozen=True)
class TemplateChild:
    attr_name: str
    template_name: str
    internal: bool
    annotation: object | None


@dataclass(slots=True, frozen=True)
class TemplateSignal:
    object_id: str | None
    signal_name: str
    handler_name: str
    after: bool
    swapped: bool
    connect_object_id: str | None


@dataclass(slots=True, frozen=True)
class _ChildType:
    name: str | None = None
    internal: bool = False


if TYPE_CHECKING:
    # For type checkers, Child() returns Any so that annotated assignments like
    #   button: Gtk.Button = Child()
    # do not produce an incompatible-types error — the annotation drives the type.
    def Child(name: str | None = None, *, internal: bool = False) -> Any: ...
else:
    Child = _ChildType


def _gtk_bucket(owner: Any) -> dict[str, object]:
    extensions = owner.gimeta.extensions
    bucket = extensions.get("Gtk")
    if isinstance(bucket, dict):
        return bucket
    new_bucket: dict[str, object] = {}
    extensions["Gtk"] = new_bucket
    return new_bucket


def _core_bucket(owner: Any) -> dict[str, object]:
    extensions = owner.gimeta.extensions
    bucket = extensions.get("core")
    if isinstance(bucket, dict):
        return bucket
    new_bucket: dict[str, object] = {}
    extensions["core"] = new_bucket
    return new_bucket


def _set_runtime(owner: type[object], runtime: TemplateRuntime) -> None:
    _gtk_bucket(owner)[_TEMPLATE_RUNTIME_KEY] = runtime


def _existing_runtime_for_class(owner: type[object]) -> TemplateRuntime | None:
    gimeta = getattr(owner, "gimeta", None)
    if gimeta is None:
        return None
    bucket = gimeta.extensions.get("Gtk")
    if not isinstance(bucket, dict):
        return None
    runtime = bucket.get(_TEMPLATE_RUNTIME_KEY)
    if isinstance(runtime, TemplateRuntime):
        return runtime
    return None


def _runtime_for_class(owner: type[object]) -> TemplateRuntime | None:
    for cls in owner.__mro__:
        runtime = _existing_runtime_for_class(cls)
        if runtime is not None:
            return runtime
    return None


def _runtime_for_instance(instance: object) -> TemplateRuntime:
    runtime = _runtime_for_class(type(instance))
    if runtime is None:
        raise RuntimeError("Gtk.Template runtime missing from gimeta.extensions")
    return runtime


def _push_active_template_instance(instance: object) -> None:
    try:
        stack = _active_template_instance.stack
    except AttributeError:
        stack = []
        _active_template_instance.stack = stack
    stack.append(instance)


def _pop_active_template_instance() -> None:
    try:
        stack = _active_template_instance.stack
    except AttributeError:
        return
    if stack:
        stack.pop()


def _register_post_construct_hook(
    owner: type[object], hook: Callable[[object], None]
) -> None:
    bucket = _core_bucket(owner)
    hooks = bucket.get(_POST_CONSTRUCT_HOOKS_KEY)
    if isinstance(hooks, list):
        hooks.append(hook)
        return
    bucket[_POST_CONSTRUCT_HOOKS_KEY] = [hook]


def _extract_handler_and_args(
    owner: object | Mapping[str, object], handler_name: str
) -> tuple[Callable[..., object], tuple[object, ...]]:
    if isinstance(owner, abc.Mapping):
        handler = owner.get(handler_name)
    else:
        handler = getattr(owner, handler_name, None)

    if handler is None:
        raise AttributeError(f"Handler {handler_name} not found")

    extra_args: tuple[object, ...] = ()
    if isinstance(handler, abc.Sequence) and not isinstance(handler, (str, bytes)):
        if len(handler) == 0:
            raise TypeError(f"Handler {handler!r} tuple can not be empty")
        extra_args = tuple(handler[1:])
        handler = handler[0]

    if not callable(handler):
        raise TypeError(f"Handler {handler!r} is not a method, function or tuple")

    return handler, extra_args


def _parse_template_root(data: bytes) -> ElementTree.Element:
    return ElementTree.fromstring(data.decode("utf-8"))


def _parse_template_signals(root: ElementTree.Element) -> list[TemplateSignal]:
    signals: list[TemplateSignal] = []
    for obj in root.iter("object"):
        object_id = obj.attrib.get("id")
        for signal in obj.findall("signal"):
            signals.append(
                TemplateSignal(
                    object_id=object_id,
                    signal_name=signal.attrib["name"],
                    handler_name=signal.attrib["handler"],
                    after=signal.attrib.get("after") == "yes",
                    swapped=signal.attrib.get("swapped") == "yes",
                    connect_object_id=signal.attrib.get("object"),
                )
            )
    return signals


def _validate_resource_path(path: str) -> None:
    try:
        Gio.resources_get_info(path, Gio.ResourceLookupFlags.NONE)
    except GLib.Error:
        Gio.resources_lookup_data(path, Gio.ResourceLookupFlags.NONE)


def _load_template_bytes(source: TemplateSource) -> bytes:
    if source.kind == "string":
        value = source.value
        return value.encode("utf-8") if isinstance(value, str) else value
    if source.kind == "resource_path":
        resource_path = source.value
        if not isinstance(resource_path, str):
            raise TypeError("resource_path must be a string")
        _validate_resource_path(resource_path)
        data = Gio.resources_lookup_data(
            resource_path, Gio.ResourceLookupFlags.NONE
        ).get_data()
        return bytes(data)

    filename = source.value
    if not isinstance(filename, str):
        raise TypeError("filename must be a string path")
    file_ = Gio.File.new_for_path(os.fspath(filename))
    return bytes(file_.load_contents()[1])


def _prepare_template_bytes(
    source: TemplateSource, cls: Any
) -> tuple[bytes, list[TemplateSignal]]:
    root = _parse_template_root(_load_template_bytes(source))
    template = root.find("template")
    if template is None:
        raise TypeError("Template XML must contain a <template> node")
    template.attrib["class"] = cls.gimeta.type_name
    return ElementTree.tostring(root, encoding="utf-8"), _parse_template_signals(root)


def _collect_template_children(cls: type[object]) -> list[TemplateChild]:
    annotations = getattr(cls, "__annotations__", {})
    children: list[TemplateChild] = []
    seen_template_names: dict[str, str] = {}

    def _add(attr_name: str, template_name: str, internal: bool) -> None:
        existing = seen_template_names.get(template_name)
        if existing is not None:
            raise RuntimeError(
                f"Error while exposing child {template_name!r} as {attr_name!r}, "
                f"already available as {existing!r}"
            )
        seen_template_names[template_name] = attr_name
        children.append(
            TemplateChild(
                attr_name=attr_name,
                template_name=template_name,
                internal=internal,
                annotation=annotations.get(attr_name),
            )
        )

    # Explicit Child() instances take priority.
    for attr_name, value in cls.__dict__.items():
        if isinstance(value, _ChildType):
            _add(attr_name, value.name or attr_name, value.internal)

    # Implicit binding: plain type annotations with no Child() value are also
    # treated as template children (annotation drives the widget type).
    for attr_name in annotations:
        if attr_name in seen_template_names:
            continue  # already registered via explicit Child()
        if attr_name.startswith("_") or attr_name in cls.__dict__:
            continue  # private or has a non-Child runtime value
        _add(attr_name, attr_name, False)

    return children


def _builder_scope_type() -> type[object]:
    global _builder_scope_cls
    if _builder_scope_cls is not None:
        return _builder_scope_cls

    from ginext import Gtk

    class TemplateBuilderScope(Gtk.BuilderCScope):
        def do_create_closure(
            self, builder: Any, func_name: object, flags: int, obj: object
        ) -> object:
            current_object = builder.get_current_object()
            runtime = _runtime_for_class(type(current_object))
            if runtime is None:
                # Internal GTK/Adw composite widget closures — not ours to handle.
                return None
            try:
                return runtime.create_closure(
                    current_object=current_object,
                    func_name=str(func_name),
                    flags=flags,
                    connect_object=obj,
                )
            except RuntimeError:
                return None

    _builder_scope_cls = TemplateBuilderScope
    return TemplateBuilderScope


def _builder_scope() -> object:
    return _builder_scope_type()()


@dataclass(slots=True)
class TemplateRuntime:
    cls: Any
    source: TemplateSource
    children: list[TemplateChild]
    signals: list[TemplateSignal]
    base_init_template: Callable[[Any], object]
    validate: TemplateValidation = "strict"
    connect_signals: bool = True

    def bind_class(self) -> None:
        from ginext import Gtk

        for child in self.children:
            self.cls.bind_template_child_full(child.template_name, child.internal, 0)

        runtime = self

        def init_template(instance: object) -> None:
            runtime.init_instance(instance)

        self.cls.init_template = init_template
        _register_post_construct_hook(self.cls, self.init_instance)

        if not self.connect_signals:
            return
        if Gtk.__version__[0] == 4:
            self.cls.set_template_scope(_builder_scope())
            return

        def connect_func(
            builder: object,
            obj: object,
            signal_name: object,
            handler_name: object,
            connect_object: object,
            flags: int,
        ) -> None:
            return None

        self.cls.set_connect_func(connect_func)

    def init_instance(self, instance: Any) -> None:
        if instance.__dict__.get(_INITIALIZED_ATTR):
            return
        instance.__dict__[_INITIALIZED_ATTR] = True

        if instance.__class__ is not self.cls:
            raise TypeError(
                "Inheritance from classes with @Gtk.Template decorators "
                "is not allowed at this time"
            )

        _push_active_template_instance(instance)
        try:
            self.base_init_template(instance)
            for child in self.children:
                instance.__dict__[child.attr_name] = instance.get_template_child(
                    self.cls.gimeta.gtype, child.template_name
                )
            if self.connect_signals:
                self.connect_instance_signals(instance)
        finally:
            _pop_active_template_instance()

    def resolve_handler(
        self, instance: object, handler_name: str
    ) -> tuple[Callable[..., object], tuple[object, ...]]:
        return _extract_handler_and_args(instance, handler_name)

    def _signal_handler(
        self,
        *,
        instance: object,
        handler_name: str,
        connect_object: object,
        drop_source: bool,
    ) -> Callable[..., object]:
        handler, extra_args = self.resolve_handler(instance, handler_name)
        if connect_object is not None:
            if drop_source:

                def drop_source_callback(
                    _source: object, *signal_args: object
                ) -> object:
                    return handler(*extra_args, connect_object, *signal_args)

                return drop_source_callback

            def keep_source_callback(*signal_args: object) -> object:
                return handler(*extra_args, connect_object, *signal_args[1:])

            return keep_source_callback

        def plain_callback(*signal_args: object) -> object:
            return handler(*extra_args, *signal_args)

        return plain_callback

    def create_closure(
        self,
        *,
        current_object: object,
        func_name: str,
        flags: int,
        connect_object: object,
    ) -> object:

        swapped = int(flags & _CONNECT_SWAPPED)
        if swapped:
            raise RuntimeError("GObject.ConnectFlags.SWAPPED not supported")

        closure = self._signal_handler(
            instance=current_object,
            handler_name=func_name,
            connect_object=connect_object,
            drop_source=False,
        )
        return closure

    def _resolve_instance_signal_object(
        self, instance: Any, object_id: str | None, *, default_to_instance: bool
    ) -> object | None:
        if object_id is None:
            if default_to_instance:
                return cast("object", instance)
            return None
        if object_id == self.cls.gimeta.type_name:
            return cast("object", instance)
        for child in self.children:
            if child.template_name == object_id:
                return cast("object", instance.__dict__[child.attr_name])
        obj = instance.get_template_child(self.cls.gimeta.gtype, object_id)
        if obj is None:
            raise AttributeError(
                f"Gtk.Template child {object_id!r} not found on {self.cls.__name__}"
            )
        return cast("object", obj)

    def connect_instance_signals(self, instance: Any) -> None:
        from ginext.signal.adapt import _SIGNAL_ARG_LIMIT_ATTR

        for signal in self.signals:
            obj = self._resolve_instance_signal_object(
                instance, signal.object_id, default_to_instance=True
            )
            connect_object = self._resolve_instance_signal_object(
                instance, signal.connect_object_id, default_to_instance=False
            )
            if signal.swapped:
                raise RuntimeError("GObject.ConnectFlags.SWAPPED not supported")
            callback = self._signal_handler(
                instance=instance,
                handler_name=signal.handler_name,
                connect_object=connect_object,
                drop_source=True,
            )
            if connect_object is not None:
                setattr(callback, _SIGNAL_ARG_LIMIT_ATTR, None)
            cast("Any", obj).signal_for_name(signal.signal_name).connect(
                callback,
                after=signal.after,
                owner=instance,
            )


@dataclass(slots=True)
@dataclass_transform(field_specifiers=(Child,))
class Template:
    source: TemplateSource
    validate: TemplateValidation = "strict"
    connect_signals: bool = True

    Child = Child

    def __init__(
        self,
        *,
        string: str | bytes | None = None,
        filename: str | os.PathLike[str] | None = None,
        resource_path: str | None = None,
        validate: TemplateValidation = "strict",
        connect_signals: bool = True,
    ) -> None:
        provided = [value is not None for value in (string, filename, resource_path)]
        if sum(provided) != 1:
            raise TypeError(
                "Requires exactly one of the following arguments: "
                "string, filename, resource_path"
            )

        if string is not None:
            source = TemplateSource("string", string)
        elif filename is not None:
            source = TemplateSource("filename", os.fspath(filename))
        else:
            assert resource_path is not None
            source = TemplateSource("resource_path", resource_path)

        self.source = source
        self.validate = validate
        self.connect_signals = connect_signals

    def __call__(self, cls: type[WidgetT]) -> type[WidgetT]:
        from ginext import Gtk

        if not issubclass(cls, Gtk.Widget):
            raise TypeError("Can only use @Gtk.Template on Widgets")
        if _runtime_for_class(cls) is not None:
            raise TypeError("Cannot nest template classes")

        template_bytes, signals = _prepare_template_bytes(self.source, cls)
        template_cls = cast("_TemplateWidgetType", cls)
        runtime = TemplateRuntime(
            cls=cls,
            source=self.source,
            children=_collect_template_children(cls),
            signals=signals,
            base_init_template=template_cls.init_template,
            validate=self.validate,
            connect_signals=self.connect_signals,
        )
        _set_runtime(cls, runtime)
        template_cls.set_template(GLib.Bytes.new(template_bytes))
        runtime.bind_class()
        return cls
