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

import enum
import inspect
import os
import sys
import warnings
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from .. import private
from ..errors import Error as _GLibError
from ..errors import install_glib_error_class as _install_glib_error_class
from ginext import GLib

if TYPE_CHECKING:
    from ..overlay.registrar import OverlayRegistrar


overlay: OverlayRegistrar = GLib.overlay
overlay.constant("Error", _GLibError)
overlay.constant("GError", _GLibError)

# GLib.Error is raised by GError-throwing methods: it must inherit from
# Exception so it can be caught as a Python exception.
overlay.bases("Error", ["Exception"])


@overlay.replace
def path_get_basename(fn: Any, file_name: str | bytes) -> str:
    """Return the last component of a filename (accepts str or path-like)."""
    return str(fn(os.fspath(file_name)))


@overlay.method("Source")
def __init__(self: object) -> None:
    # ginext constructs GLib.Source subclasses via __new__ (C-level allocation);
    # __init__ is a no-op for Python-defined subclasses.
    pass


def _register_glib_unix_deprecations() -> None:
    try:
        _ginext = sys.modules["ginext"]
        version = _ginext.defaults.resolve_version("GLibUnix")
        # Use PYGOBJECT profile so that the deprecated values are identical
        # objects to gi.repository.GLibUnix.* (same profile, same type cache).
        GLibUnix = _ginext._load_namespace(
            "GLibUnix", version, profile=_ginext.abi.PYGOBJECT
        )
        unix_names = set(private.namespace_dir("GLibUnix", version))
    except (ImportError, AttributeError, LookupError):
        # GLibUnix is absent on non-Unix platforms (e.g. Windows uses GLibWin32).
        return
    overlay.deprecated("UnixPipe", GLibUnix.Pipe, "GLibUnix.Pipe")
    overlay.deprecated("UnixPipeEnd", GLibUnix.PipeEnd, "GLibUnix.PipeEnd")
    overlay.deprecated("closefrom", GLibUnix.closefrom, "GLibUnix.closefrom")
    overlay.deprecated("unix_error_quark", GLibUnix.error_quark, "GLibUnix.error_quark")
    overlay.deprecated("unix_fd_add_full", GLibUnix.fd_add_full, "GLibUnix.fd_add_full")
    overlay.deprecated(
        "unix_fd_source_new", GLibUnix.fd_source_new, "GLibUnix.fd_source_new"
    )
    overlay.deprecated(
        "fdwalk_set_cloexec", GLibUnix.fdwalk_set_cloexec, "GLibUnix.fdwalk_set_cloexec"
    )
    overlay.deprecated(
        "unix_get_passwd_entry", GLibUnix.get_passwd_entry, "GLibUnix.get_passwd_entry"
    )
    overlay.deprecated("unix_open_pipe", GLibUnix.open_pipe, "GLibUnix.open_pipe")
    overlay.deprecated(
        "unix_set_fd_nonblocking",
        GLibUnix.set_fd_nonblocking,
        "GLibUnix.set_fd_nonblocking",
    )
    overlay.deprecated(
        "unix_signal_source_new",
        GLibUnix.signal_source_new,
        "GLibUnix.signal_source_new",
    )
    if "fd_query_path" in unix_names:
        overlay.deprecated(
            "unix_fd_query_path", GLibUnix.fd_query_path, "GLibUnix.fd_query_path"
        )
    if "signal_add" in unix_names:
        overlay.deprecated(
            "unix_signal_add", GLibUnix.signal_add, "GLibUnix.signal_add"
        )
        overlay.deprecated(
            "unix_signal_add_full", GLibUnix.signal_add, "GLibUnix.signal_add"
        )
    else:
        overlay.deprecated(
            "unix_signal_add_full", GLibUnix.signal_add_full, "GLibUnix.signal_add_full"
        )


_install_glib_error_class(GLib)

# GLib.MainLoop() with no args → g_main_loop_new(NULL, FALSE)
overlay.defaults("MainLoop", "new", context=None, is_running=False)


@overlay.replace
def idle_add(
    fn: Any,
    function: Any,
    *user_data: Any,
    priority: int = GLib.PRIORITY_DEFAULT_IDLE,
) -> Any:
    def callback() -> Any:
        return function(*user_data)

    return fn(priority, callback)


_idle_add: Any = idle_add
_idle_add.__text_signature__ = "(function, *, priority=200)"
_idle_add.__signature__ = inspect.Signature(
    [
        inspect.Parameter("function", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        inspect.Parameter(
            "priority",
            inspect.Parameter.KEYWORD_ONLY,
            default=GLib.PRIORITY_DEFAULT_IDLE,
        ),
    ]
)


@overlay.replace
def timeout_add(
    fn: Any,
    interval: int,
    function: Any,
    *user_data: Any,
    priority: int = GLib.PRIORITY_DEFAULT,
) -> Any:
    def callback() -> Any:
        return function(*user_data)

    return fn(priority, interval, callback)


@overlay.replace
def timeout_add_seconds(
    fn: Any,
    interval: int,
    function: Any,
    *user_data: Any,
    priority: int = GLib.PRIORITY_DEFAULT,
) -> Any:
    def callback() -> Any:
        return function(*user_data)

    return fn(priority, interval, callback)


def _child_watch_add_get_args(
    priority_or_pid: Any, pid_or_callback: Any, *args: Any, **kwargs: Any
) -> tuple[Any, Any, Any, tuple[Any, ...]]:
    user_data: tuple[Any, ...] = ()

    if callable(pid_or_callback):
        _W: type[Warning]
        try:
            from gi import PyGIDeprecationWarning as _pygi_w

            _W = _pygi_w
        except ImportError:
            _W = DeprecationWarning
        warnings.warn(
            "Calling child_watch_add without priority as first argument is deprecated",
            _W,
            stacklevel=2,
        )
        pid = priority_or_pid
        callback = pid_or_callback
        if len(args) == 0:
            priority = kwargs.get("priority", GLib.PRIORITY_DEFAULT)
        elif len(args) == 1:
            user_data = args
            priority = kwargs.get("priority", GLib.PRIORITY_DEFAULT)
        elif len(args) == 2:
            user_data = (args[0],)
            priority = args[1]
        else:
            raise TypeError("expected at most 4 positional arguments")
    else:
        priority = priority_or_pid
        pid = pid_or_callback
        if "function" in kwargs:
            callback = kwargs["function"]
            user_data = args
        elif len(args) > 0 and callable(args[0]):
            callback = args[0]
            user_data = args[1:]
        else:
            raise TypeError("expected callback as third argument")

    if "data" in kwargs:
        if user_data:
            raise TypeError('got multiple values for "data" argument')
        user_data = (kwargs["data"],)

    return priority, pid, callback, user_data


overlay.constant("_child_watch_add_get_args", _child_watch_add_get_args)


@overlay.replace
def child_watch_add(fn: Any, *args: Any, **kwargs: Any) -> Any:
    priority, pid, function, data = _child_watch_add_get_args(*args, **kwargs)

    def callback(pid: Any, status: Any) -> Any:
        return function(pid, status, *data)

    return fn(priority, pid, callback)


@overlay.replace
def log_set_writer_func(fn: Any, func: object = None, user_data: object = None) -> None:
    """Install a log writer function with an optional user_data argument."""
    fn(func, user_data)


@overlay.add
def threads_init() -> None:
    _W: type[Warning]
    try:
        from gi import PyGIDeprecationWarning as _pygi_w

        _W = _pygi_w
    except ImportError:
        _W = DeprecationWarning
    warnings.warn(
        "GLib.threads_init() is not needed since GLib 2.32, do not call it",
        _W,
        stacklevel=2,
    )


@overlay.replace
def markup_escape_text(fn: Any, text: object, length: int = -1) -> Any:
    if isinstance(text, (bytes, bytearray)) and length >= 0:
        text = bytes(text[:length])
        length = -1
    return fn(text, length)


@overlay.replace
def filename_from_utf8(fn: Any, utf8string: object, len_: int = -1) -> Any:
    return fn(utf8string, len_)


@overlay.replace
def get_current_time() -> float:
    _W: type[Warning]
    try:
        from gi import PyGIDeprecationWarning as _pygi_w

        _W = _pygi_w
    except ImportError:
        _W = DeprecationWarning
    warnings.warn(
        "GLib.get_current_time() is deprecated; use GLib.get_real_time() instead",
        _W,
        stacklevel=2,
    )
    return float(GLib.get_real_time()) / 1e6


@overlay.replace
def strcasecmp(fn: Any, s1: object, s2: object) -> Any:
    warnings.warn("GLib.strcasecmp is deprecated", DeprecationWarning, stacklevel=3)
    return fn(s1, s2)


def _io_add_watch_get_args(
    channel: Any,
    priority_or_condition: Any,
    condition_or_func: Any,
    *args: Any,
    **kwargs: Any,
) -> tuple[Any, Any, Any, Any, tuple[Any, ...]]:
    _W: type[Warning]
    try:
        from gi import PyGIDeprecationWarning as _pygi_w

        _W = _pygi_w
    except ImportError:
        _W = DeprecationWarning

    if isinstance(priority_or_condition, enum.IntFlag):
        # Old style: (channel, condition, func, *user_data, priority=P_DEFAULT)
        condition = priority_or_condition
        func = condition_or_func
        if not callable(func):
            raise TypeError(f"argument 3 must be callable, not {type(func).__name__}")
        priority = kwargs.pop("priority", GLib.PRIORITY_DEFAULT)
        user_data: tuple[Any, ...] = args
    else:
        # New style: (channel, priority, condition, func, *user_data)
        priority = priority_or_condition
        condition = condition_or_func
        if not isinstance(condition, enum.IntFlag):
            raise TypeError(
                f"argument 3 must be GLib.IOCondition, not {type(condition).__name__}"
            )
        if not args or not callable(args[0]):
            raise TypeError("argument 4 must be callable")
        func = args[0]
        user_data = args[1:]

    if isinstance(channel, int):
        warnings.warn(
            "Passing an fd to io_add_watch is deprecated, use GLib.IOChannel(filedes=fd)",
            _W,
            stacklevel=3,
        )
        channel = _io_channel_from_fd(channel, is_socket=False)
    elif hasattr(channel, "fileno"):
        warnings.warn(
            "Passing a Python file to io_add_watch is deprecated, "
            "use GLib.IOChannel(filedes=file.fileno())",
            _W,
            stacklevel=3,
        )
        import socket as _socket

        channel = _io_channel_from_fd(
            channel.fileno(), is_socket=isinstance(channel, _socket.socket)
        )

    return channel, priority, condition, func, user_data


def _io_channel_from_fd(fd: int, *, is_socket: bool) -> Any:
    # g_io_channel_unix_new is POSIX-only. On Windows GLib distinguishes
    # sockets (win32_new_socket, takes a SOCKET) from CRT fds (win32_new_fd);
    # using unix_new on a Windows socket fd produces a broken channel that
    # crashes on use. unix_new and the win32_new_* methods are each absent from
    # the other platform's typelib (and thus its generated stubs), so go through
    # an Any alias to keep mypy --strict happy on both.
    io_channel: Any = GLib.IOChannel
    if sys.platform == "win32":
        if is_socket:
            return io_channel.win32_new_socket(fd)
        return io_channel.win32_new_fd(fd)
    return io_channel.unix_new(fd)


@overlay.constructor("IOChannel")
def _io_channel_new(
    cls: Any,
    filedes: int | None = None,
    filename: str | None = None,
    mode: str | None = None,
    hwnd: int | None = None,
) -> Any:
    # pygobject-compat GLib.IOChannel(...) constructor. filedes routes through
    # the platform-correct backend (win32 vs unix); `hwnd` is pygobject's name
    # for a win32 CRT fd (it maps to g_io_channel_win32_new_fd, despite the
    # name). Mirrors gi/overrides/GLib.py.
    if filename is not None:
        return GLib.IOChannel.new_file(filename, mode or "r")
    if filedes is not None:
        return _io_channel_from_fd(filedes, is_socket=False)
    if hwnd is not None:
        # win32-only; absent from non-Windows stubs (see _io_channel_from_fd).
        io_channel: Any = GLib.IOChannel
        return io_channel.win32_new_fd(hwnd)
    raise TypeError(
        "GLib.IOChannel: a filename, file descriptor, or window handle is required"
    )


overlay.constant("_io_add_watch_get_args", _io_add_watch_get_args)


@overlay.replace
def io_add_watch(
    fn: Any,
    channel_or_fd: Any,
    priority_or_condition: Any,
    condition_or_func: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    channel, priority, condition, func, user_data = _io_add_watch_get_args(
        channel_or_fd, priority_or_condition, condition_or_func, *args, **kwargs
    )
    original = channel_or_fd

    def _callback(inner_channel: Any, inner_condition: Any, _user_data: Any) -> Any:
        return func(original, inner_condition, *user_data)

    return fn(channel, priority, condition, _callback, None)


@overlay.method("Date")
def set_time(fn: Any, self: Any, time_: object) -> Any:
    warnings.warn("GLib.Date.set_time is deprecated", DeprecationWarning, stacklevel=3)
    return fn(self, time_)


def _variant_signature_head(signature: str) -> tuple[str, str]:
    if not signature:
        raise TypeError("empty GVariant signature")
    head = signature[0]
    if head in "bynqiuxtdhsogv":
        return head, signature[1:]
    if head in "am":
        child, rest = _variant_signature_head(signature[1:])
        return head + child, rest
    if head in "({":
        close = ")" if head == "(" else "}"
        depth = 1
        i = 1
        while i < len(signature) and depth:
            ch = signature[i]
            if ch == head:
                depth += 1
            elif ch == close:
                depth -= 1
            elif ch in "({":
                child, rest = _variant_signature_head(signature[i:])
                i = len(signature) - len(rest)
                continue
            i += 1
        if depth:
            raise TypeError("Invalid GVariant format string %r" % (signature,))
        return signature[:i], signature[i:]
    raise TypeError("Invalid GVariant format string %r" % (signature,))


def _split_variant_tuple_signature(signature: str) -> list[str]:
    parts: list[str] = []
    rest = signature
    while rest:
        part, rest = _variant_signature_head(rest)
        parts.append(part)
    return parts


@overlay.method("Variant", name="split_signature", as_staticmethod=True)
def _variant_split_signature(signature: str) -> list[str]:
    if signature.startswith("(") and signature.endswith(")"):
        signature = signature[1:-1]
    return _split_variant_tuple_signature(signature)


def _variant_dict_entry_signatures(signature: str) -> tuple[str, str]:
    if not (signature.startswith("{") and signature.endswith("}")):
        raise TypeError("GVariant format %r is not a dict entry" % (signature,))
    parts = _split_variant_tuple_signature(signature[1:-1])
    if len(parts) != 2:
        raise TypeError("Invalid GVariant dict-entry format %r" % (signature,))
    return parts[0], parts[1]


_variant_simple_constructor_names = {
    "b": "new_boolean",
    "y": "new_byte",
    "n": "new_int16",
    "q": "new_uint16",
    "i": "new_int32",
    "u": "new_uint32",
    "x": "new_int64",
    "t": "new_uint64",
    "h": "new_handle",
    "d": "new_double",
    "s": "new_string",
    "o": "new_object_path",
    "g": "new_signature",
}


def _variant_type(signature: str) -> Any:
    return GLib.VariantType.new(signature)


def _variant_new_tuple_from_children(children: Any) -> Any:
    children = tuple(children)
    return GLib.Variant.gimeta.typelib_methods["new_tuple"](list(children))


def _variant_array_values(format_string: str, value: Any) -> Any:
    if format_string == "ay":
        if isinstance(value, str):
            return value.encode()
        if isinstance(value, (bytes, bytearray)):
            return value
    return value


def _variant_from_python(format_string: str, value: Any) -> Any:
    if not isinstance(format_string, str):
        raise TypeError("bad argument type for built-in operation")
    if not GLib.VariantType.string_is_valid(format_string):
        raise TypeError("Invalid GVariant format string %r" % (format_string,))
    head = format_string[:1]
    if head == "m":
        element_signature = format_string[1:]
        child = (
            None if value is None else _variant_from_python(element_signature, value)
        )
        return GLib.Variant.new_maybe(_variant_type(element_signature), child)
    if head == "a":
        element_signature = format_string[1:]
        element_type = _variant_type(element_signature)
        source = _variant_array_values(format_string, value)
        if element_signature.startswith("{") and isinstance(source, Mapping):
            key_signature, value_signature = _variant_dict_entry_signatures(
                element_signature
            )
            children = [
                GLib.Variant.new_dict_entry(
                    _variant_from_python(key_signature, key),
                    _variant_from_python(value_signature, item),
                )
                for key, item in source.items()
            ]
        else:
            try:
                children = [
                    _variant_from_python(element_signature, item) for item in source
                ]
            except TypeError as exc:
                raise TypeError("array variant value must be iterable") from exc
        return GLib.Variant.new_array(element_type, children)
    if head == "v":
        if not isinstance(value, GLib.Variant):
            raise TypeError("variant value must be a GLib.Variant")
        return GLib.Variant.new_variant(value)
    if head == "(":
        child_signatures = _split_variant_tuple_signature(format_string[1:-1])
        if not isinstance(value, (tuple, list)):
            raise TypeError("tuple variant value must be a tuple or list")
        if len(value) != len(child_signatures):
            raise TypeError("tuple variant value has wrong length")
        children = [
            _variant_from_python(child_signature, child_value)
            for child_signature, child_value in zip(
                child_signatures, value, strict=False
            )
        ]
        return _variant_new_tuple_from_children(children)
    if head == "{":
        key_signature, value_signature = _variant_dict_entry_signatures(format_string)
        try:
            key, item = tuple(value)
        except ValueError as exc:
            raise TypeError("dict-entry variant value has wrong length") from exc
        return GLib.Variant.new_dict_entry(
            _variant_from_python(key_signature, key),
            _variant_from_python(value_signature, item),
        )
    try:
        constructor = getattr(
            GLib.Variant, _variant_simple_constructor_names[format_string]
        )
    except KeyError as exc:
        raise TypeError(
            "GLib.Variant format %r is not supported" % (format_string,)
        ) from exc
    return constructor(value)


@overlay.constructor("Variant")
def _variant_new(cls: Any, *args: Any, **kwargs: Any) -> Any:
    if kwargs:
        return object.__new__(cls)
    if len(args) != 2:
        raise TypeError(
            "GLib.Variant(format_string, value) expects exactly 2 arguments"
        )
    format_string, value = args
    return _variant_from_python(format_string, value)


def _variant_freeze(value: Any) -> Any:
    if isinstance(value, tuple):
        return tuple(_variant_freeze(item) for item in value)
    if isinstance(value, list):
        return tuple(_variant_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(
            sorted(
                (_variant_freeze(key), _variant_freeze(item))
                for key, item in value.items()
            )
        )
    return value


def _variant_key(variant: Any) -> Any:
    return (variant.get_type_string(), _variant_freeze(variant.unpack()))


@overlay.method("Variant", name="__eq__")
def _variant_eq(self: Any, other: object) -> object:
    # Resolve Variant from self's own (per-profile) namespace rather than the
    # module global, so the overlay needs no namespace binding.
    variant_cls = type(self).gimeta.namespace.load_namespace().Variant
    if not isinstance(other, variant_cls):
        return NotImplemented
    return _variant_key(self) == _variant_key(other)


@overlay.method("Variant", name="__hash__")
def _variant_hash(self: Any) -> int:
    return hash(_variant_key(self))


@overlay.method("Variant", name="__bool__")
def _variant_bool(self: Any) -> bool:
    return bool(self.unpack())


@overlay.method("Variant", name="__len__")
def _variant_len(self: Any) -> int:
    type_string = self.get_type_string()
    if type_string.startswith(("a", "(", "m")):
        return int(self.n_children())
    if type_string in {"s", "o", "g"}:
        return len(self.get_string())
    raise TypeError("Variant of type %r has no len()" % (type_string,))


def _variant_dict_lookup(self: Any, key: object) -> Any:
    for i in range(self.n_children()):
        entry = self.get_child_value(i)
        entry_key = entry.get_child_value(0).unpack()
        if entry_key == key:
            return entry.get_child_value(1).unpack()
    raise KeyError(key)


@overlay.method("Variant", name="__getitem__")
def _variant_getitem(self: Any, key: object) -> Any:
    type_string = self.get_type_string()
    if type_string.startswith("a{"):
        return _variant_dict_lookup(self, key)
    if type_string in {"s", "o", "g"}:
        if not isinstance(key, int):
            raise ValueError(key)
        value = self.get_string()
        try:
            return value[key]
        except IndexError:
            raise IndexError(key) from None
    if type_string.startswith(("a", "(", "m")):
        if not isinstance(key, int):
            raise ValueError(key)
        n_children: int = self.n_children()
        idx = key + n_children if key < 0 else key
        if idx < 0 or idx >= n_children:
            raise IndexError(key)
        return self.get_child_value(idx).unpack()
    raise TypeError("Variant of type %r is not subscriptable" % (type_string,))


@overlay.method("Variant", name="__iter__")
def _variant_iter(self: Any) -> Any:
    type_string = self.get_type_string()
    if type_string in {"s", "o", "g"}:
        return iter(self.get_string())
    return (self[i] for i in range(len(self)))


@overlay.method("Variant", name="keys")
def _variant_keys(self: Any) -> list[object]:
    type_string = self.get_type_string()
    if not type_string.startswith("a{"):
        raise TypeError("GVariant type %s is not a dictionary" % type_string)
    return [
        self.get_child_value(i).get_child_value(0).unpack()
        for i in range(self.n_children())
    ]


@overlay.method("Variant", name="__repr__")
def _variant_repr(self: Any) -> str:
    return str("GLib.Variant(%r, %r)" % (self.get_type_string(), self.unpack()))


@overlay.method("Variant", name="__str__")
def _variant_str(self: Any) -> str:
    return str(self.print_(True))


def _bind_namespace(namespace: Any, fn: Any) -> Any:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        global GLib
        old = GLib
        GLib = namespace
        try:
            return fn(*args, **kwargs)
        finally:
            GLib = old

    wrapper.__name__ = fn.__name__
    return wrapper


# NOTE: Variant's __new__/__init__ are registered via @overlay.constructor and
# its other dunders (__eq__/__hash__/__repr__/__getitem__/keys/split_signature/
# ...) via @overlay.method, so they install at class-build time and need no
# apply_to_namespace wiring.


@overlay.method("Variant", staticmethod=True)
def new_tuple(*children: Any) -> Any:
    if len(children) == 1 and not isinstance(children[0], GLib.Variant):
        children = tuple(children[0])
    return _variant_new_tuple_from_children(children)


@overlay.method("Variant")
def get_string(self: Any) -> Any:
    value = type(self).gimeta.typelib_methods["get_string"](self)
    if isinstance(value, tuple):
        return value[0]
    return value


@overlay.method("Variant")
def print_(self: Any, type_annotate: bool = False) -> Any:
    return self.print(type_annotate)


def _variant_parse_error_print_context(error: object, source_str: str) -> str:
    if not isinstance(error, _GLibError):
        raise TypeError(f"Must be GLib.Error, not {type(error).__name__}")
    if not isinstance(error.message, str):
        raise TypeError(f"Must be string, not {type(error.message).__name__}")
    if error.domain is not None and not isinstance(error.domain, str):
        raise TypeError(f"Must be string, not {type(error.domain).__name__}")
    if not isinstance(error.code, int):
        raise TypeError(f"Must be number, not {type(error.code).__name__}")
    if error.code < 0 or error.code >= 2**32 - 1:
        raise OverflowError("Error code not in range 0 to GLib.MAXUINT - 1")
    return f"{error.message} in {source_str}"


@overlay.method("Variant")
def unpack(self: Any) -> Any:
    type_string = self.get_type_string()
    head = type_string[:1]
    if head == "b":
        return self.get_boolean()
    if head == "y":
        return self.get_byte()
    if head == "n":
        return self.get_int16()
    if head == "q":
        return self.get_uint16()
    if head == "i":
        return self.get_int32()
    if head == "u":
        return self.get_uint32()
    if head == "x":
        return self.get_int64()
    if head == "t":
        return self.get_uint64()
    if head == "h":
        return self.get_handle()
    if head == "d":
        return self.get_double()
    if head in {"s", "o", "g"}:
        return self.get_string()
    if head == "v":
        return self.get_variant().unpack()
    if head == "m":
        if self.n_children() == 0:
            return None
        return self.get_child_value(0).unpack()
    if head == "a":
        if type_string.startswith("a{"):
            return {
                self.get_child_value(i)
                .get_child_value(0)
                .unpack(): self.get_child_value(i).get_child_value(1).unpack()
                for i in range(self.n_children())
            }
        return [self.get_child_value(i).unpack() for i in range(self.n_children())]
    if head in {"(", "{"}:
        return tuple(self.get_child_value(i).unpack() for i in range(self.n_children()))
    raise TypeError("GLib.Variant format %r is not supported" % (type_string,))


def _apply_late_variant_methods(namespace: Any) -> None:
    namespace.Variant.parse_error_print_context = staticmethod(
        _variant_parse_error_print_context
    )
    namespace.Variant.new_tuple = staticmethod(_bind_namespace(namespace, new_tuple))


def _apply_timezone_compat(namespace: Any) -> None:
    _TimeZone = namespace.TimeZone

    def _timezone_new(cls: object, identifier: object = None) -> Any:
        if identifier is not None:
            warnings.warn(
                "GLib.TimeZone(identifier) is deprecated; use GLib.TimeZone.new_identifier(identifier)",
                DeprecationWarning,
                stacklevel=2,
            )
            return _TimeZone.new_identifier(identifier)
        return _TimeZone.new_local()

    _TimeZone.__new__ = staticmethod(_timezone_new)


@overlay.method("Source")
def attach(fn: Any, self: Any, context: object = None) -> Any:
    return fn(self, context)


@overlay.method("Source", staticmethod=True)
def remove(fn: Any, tag: object) -> Any:
    return fn(tag)


def _make_idle_class(namespace: Any) -> type:
    class Idle:
        def __new__(cls: type) -> Any:
            return namespace.idle_source_new()

    return Idle


def apply_to_namespace(namespace: Any) -> None:
    overlay.deprecated(
        "IO_STATUS_ERROR", namespace.IOStatus.ERROR, "GLib.IOStatus.ERROR"
    )
    overlay.deprecated(
        "SPAWN_LEAVE_DESCRIPTORS_OPEN",
        namespace.SpawnFlags.LEAVE_DESCRIPTORS_OPEN,
        "GLib.SpawnFlags.LEAVE_DESCRIPTORS_OPEN",
    )
    overlay.deprecated(
        "SPAWN_DO_NOT_REAP_CHILD",
        namespace.SpawnFlags.DO_NOT_REAP_CHILD,
        "GLib.SpawnFlags.DO_NOT_REAP_CHILD",
    )
    overlay.deprecated(
        "SPAWN_SEARCH_PATH",
        namespace.SpawnFlags.SEARCH_PATH,
        "GLib.SpawnFlags.SEARCH_PATH",
    )
    overlay.deprecated(
        "SPAWN_STDOUT_TO_DEV_NULL",
        namespace.SpawnFlags.STDOUT_TO_DEV_NULL,
        "GLib.SpawnFlags.STDOUT_TO_DEV_NULL",
    )
    overlay.deprecated(
        "SPAWN_STDERR_TO_DEV_NULL",
        namespace.SpawnFlags.STDERR_TO_DEV_NULL,
        "GLib.SpawnFlags.STDERR_TO_DEV_NULL",
    )
    overlay.deprecated(
        "SPAWN_CHILD_INHERITS_STDIN",
        namespace.SpawnFlags.CHILD_INHERITS_STDIN,
        "GLib.SpawnFlags.CHILD_INHERITS_STDIN",
    )
    overlay.deprecated(
        "SPAWN_FILE_AND_ARGV_ZERO",
        namespace.SpawnFlags.FILE_AND_ARGV_ZERO,
        "GLib.SpawnFlags.FILE_AND_ARGV_ZERO",
    )
    overlay.deprecated(
        "OPTION_FLAG_HIDDEN", namespace.OptionFlags.HIDDEN, "GLib.OptionFlags.HIDDEN"
    )
    overlay.deprecated(
        "IO_FLAG_IS_WRITEABLE",
        namespace.IOFlags.IS_WRITEABLE,
        "GLib.IOFlags.IS_WRITEABLE",
    )
    overlay.deprecated(
        "IO_FLAG_NONBLOCK", namespace.IOFlags.NONBLOCK, "GLib.IOFlags.NONBLOCK"
    )
    overlay.deprecated(
        "USER_DIRECTORY_DESKTOP",
        namespace.UserDirectory.DIRECTORY_DESKTOP,
        "GLib.UserDirectory.DIRECTORY_DESKTOP",
    )
    overlay.deprecated(
        "USER_DIRECTORY_DOCUMENTS",
        namespace.UserDirectory.DIRECTORY_DOCUMENTS,
        "GLib.UserDirectory.DIRECTORY_DOCUMENTS",
    )
    overlay.deprecated(
        "USER_DIRECTORY_DOWNLOAD",
        namespace.UserDirectory.DIRECTORY_DOWNLOAD,
        "GLib.UserDirectory.DIRECTORY_DOWNLOAD",
    )
    overlay.deprecated(
        "USER_DIRECTORY_MUSIC",
        namespace.UserDirectory.DIRECTORY_MUSIC,
        "GLib.UserDirectory.DIRECTORY_MUSIC",
    )
    overlay.deprecated(
        "USER_DIRECTORY_PICTURES",
        namespace.UserDirectory.DIRECTORY_PICTURES,
        "GLib.UserDirectory.DIRECTORY_PICTURES",
    )
    overlay.deprecated(
        "USER_DIRECTORY_PUBLIC_SHARE",
        namespace.UserDirectory.DIRECTORY_PUBLIC_SHARE,
        "GLib.UserDirectory.DIRECTORY_PUBLIC_SHARE",
    )
    overlay.deprecated(
        "USER_DIRECTORY_TEMPLATES",
        namespace.UserDirectory.DIRECTORY_TEMPLATES,
        "GLib.UserDirectory.DIRECTORY_TEMPLATES",
    )
    overlay.deprecated(
        "USER_DIRECTORY_VIDEOS",
        namespace.UserDirectory.DIRECTORY_VIDEOS,
        "GLib.UserDirectory.DIRECTORY_VIDEOS",
    )
    overlay.deprecated(
        "USER_N_DIRECTORIES",
        namespace.UserDirectory.N_DIRECTORIES,
        "GLib.UserDirectory.N_DIRECTORIES",
    )
    overlay.deprecated(
        "OPTION_ERROR_BAD_VALUE",
        namespace.OptionError.BAD_VALUE,
        "GLib.OptionError.BAD_VALUE",
    )
    overlay.deprecated(
        "glib_version",
        (namespace.MAJOR_VERSION, namespace.MINOR_VERSION, namespace.MICRO_VERSION),
        "(GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION)",
    )
    overlay.deprecated("pyglib_version", (3, 52, 0), "gi.version_info")
    _register_glib_unix_deprecations()
    namespace.Idle = _make_idle_class(namespace)
    _apply_late_variant_methods(namespace)
    _apply_timezone_compat(namespace)


apply_to_namespace(GLib)


def _regex_from_py(obj: object) -> Any:
    import re as _re

    if not isinstance(obj, _re.Pattern):
        raise TypeError(f"expected re.Pattern, not {type(obj).__name__!r}")
    pattern_str = obj.pattern
    if not isinstance(pattern_str, str):
        raise TypeError("only str (not bytes) re.Pattern objects map to GLib.Regex")
    flags = obj.flags
    compile_flags = 0
    if flags & _re.IGNORECASE:
        compile_flags |= int(GLib.RegexCompileFlags.CASELESS)
    if flags & _re.MULTILINE:
        compile_flags |= int(GLib.RegexCompileFlags.MULTILINE)
    if flags & _re.DOTALL:
        compile_flags |= int(GLib.RegexCompileFlags.DOTALL)
    if flags & _re.VERBOSE:
        compile_flags |= int(GLib.RegexCompileFlags.EXTENDED)
    return GLib.Regex.new(pattern_str, compile_flags, 0)


private.register_coercion(GLib.Regex, _regex_from_py)
