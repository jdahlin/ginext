from __future__ import annotations

import os
from collections import abc
from functools import partial
from typing import Any

from gi.repository import GLib, GObject, Gio


def _extract_handler_and_args(obj_or_map, handler_name):
    if isinstance(obj_or_map, abc.Mapping):
        handler = obj_or_map.get(handler_name)
    else:
        handler = getattr(obj_or_map, handler_name, None)

    if handler is None:
        raise AttributeError(f"Handler {handler_name} not found")

    args = ()
    if isinstance(handler, abc.Sequence):
        if len(handler) == 0:
            raise TypeError(f"Handler {handler} tuple can not be empty")
        args = handler[1:]
        handler = handler[0]
    elif not callable(handler):
        raise TypeError(f"Handler {handler} is not a method, function or tuple")

    return handler, args


def define_builder_scope():
    from gi.repository import Gtk

    class BuilderScope(Gtk.BuilderCScope):
        def __init__(self, scope_object=None):
            super().__init__()
            self._scope_object = scope_object

        def do_create_closure(self, builder, function_name, flags, object):
            current_object = builder.get_current_object() or self._scope_object

            if not self._scope_object:
                current_object = builder.get_current_object()
                if function_name not in current_object.__gtktemplate_methods__:
                    return None
                current_object.__gtktemplate_handlers__.add(function_name)
                handler_name = current_object.__gtktemplate_methods__[function_name]
            else:
                current_object = self._scope_object
                handler_name = function_name

            swapped = int(flags & Gtk.BuilderClosureFlags.SWAPPED)
            if swapped:
                raise RuntimeError(f"{GObject.ConnectFlags.SWAPPED!r} not supported")

            handler, extra_args = _extract_handler_and_args(
                current_object, handler_name
            )

            if object:

                def closure(*signal_args):
                    return handler(*extra_args, object, *signal_args[1:])

            else:
                closure = partial(handler, *extra_args)

            return closure

    return BuilderScope


def connect_func(builder, obj, signal_name, handler_name, connect_object, flags, cls):
    if handler_name not in cls.__gtktemplate_methods__:
        return

    method_name = cls.__gtktemplate_methods__[handler_name]
    template_inst = builder.get_object(cls.__gtype_name__)
    template_inst.__gtktemplate_handlers__.add(handler_name)
    handler = getattr(template_inst, method_name)

    after = int(flags & GObject.ConnectFlags.AFTER)
    swapped = int(flags & GObject.ConnectFlags.SWAPPED)
    if swapped:
        raise RuntimeError(f"{GObject.ConnectFlags.SWAPPED!r} not supported")

    if connect_object is not None:
        func = obj.connect_object_after if after else obj.connect_object
        func(signal_name, handler, connect_object)
    else:
        func = obj.connect_after if after else obj.connect
        func(signal_name, handler)


def register_template(cls):
    from gi.repository import Gtk

    bound_methods = {}
    bound_widgets = {}

    for attr_name, obj in list(cls.__dict__.items()):
        if isinstance(obj, CallThing):
            setattr(cls, attr_name, obj._func)
            handler_name = obj._name or attr_name
            if handler_name in bound_methods:
                old_attr_name = bound_methods[handler_name]
                raise RuntimeError(
                    f"Error while exposing handler {handler_name!r} as {attr_name!r}, "
                    f"already available as {old_attr_name!r}"
                )
            bound_methods[handler_name] = attr_name
        elif isinstance(obj, Child):
            widget_name = obj._name or attr_name
            if widget_name in bound_widgets:
                old_attr_name = bound_widgets[widget_name]
                raise RuntimeError(
                    f"Error while exposing child {widget_name!r} as {attr_name!r}, "
                    f"already available as {old_attr_name!r}"
                )
            bound_widgets[widget_name] = attr_name
            cls.bind_template_child_full(widget_name, obj._internal, 0)

    cls.__gtktemplate_methods__ = bound_methods
    cls.__gtktemplate_widgets__ = bound_widgets

    if getattr(Gtk, "_version", "") == "4.0":
        builder_scope = define_builder_scope()()
        cls.__gtktemplate_scope__ = builder_scope
        cls.set_template_scope(builder_scope)
    else:

        def _connect_func(
            builder, obj, signal_name, handler_name, connect_object, flags
        ):
            connect_func(
                builder, obj, signal_name, handler_name, connect_object, flags, cls
            )

        cls.set_connect_func(_connect_func)

    base_init_template = cls.init_template
    cls.__dontuse_ginstance_init__ = lambda s: init_template(s, cls, base_init_template)
    cls.init_template = cls.__dontuse_ginstance_init__


def init_template(self, cls, base_init_template):
    self.init_template = lambda: None

    if self.__class__ is not cls:
        raise TypeError(
            "Inheritance from classes with @Gtk.Template decorators "
            "is not allowed at this time"
        )

    self.__gtktemplate_handlers__ = set()
    base_init_template(self)

    for widget_name, attr_name in self.__gtktemplate_widgets__.items():
        self.__dict__[attr_name] = self.get_template_child(cls, widget_name)

    for handler_name in self.__gtktemplate_methods__:
        if handler_name not in self.__gtktemplate_handlers__:
            raise RuntimeError(
                f"Handler '{handler_name}' was declared with @Gtk.Template.Callback "
                "but was not present in template"
            )


class Child:
    def __init__(self, name=None, **kwargs):
        self._name = name
        self._internal = kwargs.pop("internal", False)
        if kwargs:
            raise TypeError(f"Unhandled arguments: {kwargs!r}")


class CallThing:
    def __init__(self, name, func):
        self._name = name
        self._func = func


class Callback:
    def __init__(self, name=None):
        self._name = name

    def __call__(self, func):
        return CallThing(self._name, func)


def validate_resource_path(path):
    try:
        Gio.resources_get_info(path, Gio.ResourceLookupFlags.NONE)
    except GLib.Error:
        Gio.resources_lookup_data(path, Gio.ResourceLookupFlags.NONE)


class Template:
    def __init__(self, **kwargs: Any) -> None:
        self.string: str | bytes | None = None
        self.filename: str | os.PathLike[str] | None = None
        self.resource_path: str | None = None
        if "string" in kwargs:
            self.string = kwargs.pop("string")
        elif "filename" in kwargs:
            self.filename = kwargs.pop("filename")
        elif "resource_path" in kwargs:
            self.resource_path = kwargs.pop("resource_path")
        else:
            raise TypeError(
                "Requires one of the following arguments: "
                "string, filename, resource_path"
            )
        if kwargs:
            raise TypeError(f"Unhandled keyword arguments {kwargs!r}")

    @classmethod
    def from_file(cls, filename):
        return cls(filename=filename)

    @classmethod
    def from_string(cls, string):
        return cls(string=string)

    @classmethod
    def from_resource(cls, resource_path):
        return cls(resource_path=resource_path)

    Callback = Callback
    Child = Child

    def __call__(self, cls):
        from gi.repository import Gtk

        if not isinstance(cls, type) or not issubclass(cls, Gtk.Widget):
            raise TypeError("Can only use @Gtk.Template on Widgets")
        if "__gtype_name__" not in cls.__dict__:
            raise TypeError(
                f"{cls.__name__!r} does not have a __gtype_name__. Set it to the name "
                "of the class in your template"
            )
        if hasattr(cls, "__gtktemplate_methods__"):
            raise TypeError("Cannot nest template classes")

        if self.string is not None:
            data = (
                self.string.encode("utf-8")
                if not isinstance(self.string, bytes)
                else self.string
            )
            cls.set_template(GLib.Bytes.new(data))
            register_template(cls)
            return cls
        if self.resource_path is not None:
            validate_resource_path(self.resource_path)
            cls.set_template_from_resource(self.resource_path)
            register_template(cls)
            return cls
        assert self.filename is not None
        file_ = Gio.File.new_for_path(os.fspath(self.filename))
        cls.set_template(GLib.Bytes.new(file_.load_contents()[1]))
        register_template(cls)
        return cls


def install(namespace: object) -> object:
    _ns: Any = namespace
    _ns.Template = Template
    _ns._extract_handler_and_args = _extract_handler_and_args
    return namespace
