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

import contextlib
import os
import signal
import socket
import sys
import threading
import weakref
from typing import TYPE_CHECKING, Any, Iterator, Literal, cast

from ginext.errors import install_gio_error_classes as _install_gio_error_classes
from ginext import Gio, GLib, private
from ginext.gobject.gobjectclass import GObject as _GObject
from ginext_gio._actions import install_application_actions

if TYPE_CHECKING:
    from collections.abc import Generator


overlay = Gio.overlay


@overlay.method("Application", name="__init__")
def _application_init(self: Any, **kwargs: object) -> None:
    _GObject.__init__(self, **kwargs)
    install_application_actions(self)


def apply_to_namespace(namespace: Any) -> None:
    _install_gio_error_classes(namespace)


# Decent defaults so callers can skip the ubiquitous `flags`/`cancellable`
# noise. Declared before any method overlay so they are registered before the
# classes build. Trailing nullable args (cancellable when it is last) are
# already omittable; cancellable is defaulted explicitly only where another
# argument (a progress callback) follows it.
overlay.defaults("File", "query_info", flags=Gio.FileQueryInfoFlags.NONE)
overlay.defaults("File", "enumerate_children", flags=Gio.FileQueryInfoFlags.NONE)
overlay.defaults("File", "create", flags=Gio.FileCreateFlags.NONE)
overlay.defaults("File", "append_to", flags=Gio.FileCreateFlags.NONE)
overlay.defaults("File", "replace", flags=Gio.FileCreateFlags.NONE)
overlay.defaults("File", "copy", flags=Gio.FileCopyFlags.NONE, cancellable=None)
overlay.defaults("File", "move", flags=Gio.FileCopyFlags.NONE, cancellable=None)

# call_with_unix_fd_list_finish returns (GVariant, GUnixFDList); expose the
# OUT fd-list by name so `result.out_fd_list` works on the awaited result.
overlay.async_result("DBusProxy", "call_with_unix_fd_list", "", "out_fd_list")
overlay.async_result("DBusConnection", "call_with_unix_fd_list", "", "out_fd_list")


_RUN_ARGV_OMITTED: object = object()


@contextlib.contextmanager
def _application_sigint_handler(application: Any) -> Generator[None, None, None]:
    from ginext import GLib

    # The wakeup mechanism below relies on signal.set_wakeup_fd writing to a
    # socketpair watched via GLib.IOChannel.unix_new. That is Unix-only:
    # on Windows IOChannel.unix_new cannot watch a socket fd (it needs the
    # win32-socket channel) and the path crashes. SIGINT delivery during the
    # GLib main loop is a POSIX concern, so skip the handler on Windows.
    if sys.platform == "win32":
        yield
        return

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    old_handler = signal.getsignal(signal.SIGINT)
    if old_handler is not signal.default_int_handler:
        yield
        return

    application_ref: weakref.ref[Any] = weakref.ref(application)
    sigint_seen = False
    read_socket, write_socket = socket.socketpair()

    with contextlib.closing(read_socket), contextlib.closing(write_socket):
        for sock in (read_socket, write_socket):
            sock.setblocking(False)
            sock.set_inheritable(False)

        old_wakeup_fd = signal.set_wakeup_fd(
            write_socket.fileno(),
            warn_on_full_buffer=False,
        )

        def on_sigint(_signum: int, _frame: Any) -> None:
            nonlocal sigint_seen
            sigint_seen = True
            app = application_ref()
            if app is not None:
                app.quit()

        signal.signal(signal.SIGINT, on_sigint)

        def on_wakeup(_source: Any, condition: Any) -> Any:
            if condition & GLib.IOCondition.IN:
                try:
                    while read_socket.recv(4096):
                        pass
                except BlockingIOError:
                    pass
            return GLib.SOURCE_CONTINUE

        source_id = GLib.io_add_watch(
            GLib.IOChannel.unix_new(read_socket.fileno()),
            GLib.PRIORITY_DEFAULT,
            (
                GLib.IOCondition.IN
                | GLib.IOCondition.HUP
                | GLib.IOCondition.NVAL
                | GLib.IOCondition.ERR
            ),
            on_wakeup,
        )
        try:
            yield
        finally:
            GLib.source_remove(source_id)
            signal.signal(signal.SIGINT, old_handler)
            signal.set_wakeup_fd(old_wakeup_fd)

    if sigint_seen:
        raise KeyboardInterrupt


@overlay.method("Application")
def run(
    fn: Any,
    self: Any,
    argv: Any = _RUN_ARGV_OMITTED,
    *,
    install_signal_handler: bool = True,
) -> int:
    if not install_signal_handler:
        if argv is _RUN_ARGV_OMITTED:
            return int(fn(self))
        return int(fn(self, argv))

    with _application_sigint_handler(self):
        if argv is _RUN_ARGV_OMITTED:
            return int(fn(self))
        return int(fn(self, argv))


def _register_gio_unix_deprecations() -> None:
    try:
        import ginext as _ginext

        version = _ginext.defaults.resolve_version("GioUnix")
        if version is None:
            return
        # Use PYGOBJECT profile so deprecated values match gi.repository.GioUnix.*
        GioUnix = _ginext._load_namespace(
            "GioUnix", version, profile=_ginext.abi.PYGOBJECT
        )
    except (ImportError, AttributeError, RuntimeError, LookupError):
        return
    # GioUnix exposes a platform-dependent subset of these symbols: e.g.
    # DesktopAppInfo and the Unix{Input,Output}Stream types are absent on
    # macOS. Register a deprecation alias only when the underlying symbol
    # exists so the overlay still loads on platforms with a smaller GioUnix.
    deprecations = (
        ("DesktopAppInfo", "DesktopAppInfo"),
        ("unix_mount_points_get", "mount_points_get"),
        ("UnixInputStream", "InputStream"),
        ("UnixOutputStream", "OutputStream"),
        ("UnixInputStreamClass", "InputStreamClass"),
        ("UnixOutputStreamClass", "OutputStreamClass"),
        ("UnixMountMonitor", "MountMonitor"),
    )
    for alias, attr in deprecations:
        try:
            value = getattr(GioUnix, attr)
        except AttributeError:
            continue
        overlay.deprecated(alias, value, f"GioUnix.{attr}")


_register_gio_unix_deprecations()


@overlay.replace
def resources_lookup_data(fn: Any, path: str, lookup_flags: Any) -> GLib.Bytes:
    """Look up data in registered resources; returns a GLib.Bytes object."""
    result: GLib.Bytes = fn(path, lookup_flags)
    return result


# GListModel accessors are kept here for Python collection protocol
# behavior; interface methods themselves are available on implementing
# classes through the built MRO.
def _n_items(store: Any) -> int:
    return int(private.invoke(Gio, "ListModel.get_n_items", store))


def _item_at(store: Any, index: int) -> Any:
    return private.invoke(Gio, "ListModel.get_item", store, index)


def _normalize_index(index: int, length: int) -> int:
    if index < 0:
        index += length
    if index < 0 or index >= length:
        raise IndexError("list store index out of range")
    return index


def _normalize_position(index: int, length: int) -> int:
    if index < 0:
        index += length
    if index < 0 or index >= length:
        raise IndexError("index out of range")
    return index


@overlay.method("ListModel")
def __len__(self: Any) -> int:
    return _n_items(self)


@overlay.method("ListModel")
def __bool__(self: Any) -> bool:
    return _n_items(self) > 0


@overlay.method("ListModel")
def __getitem__(self: Any, key: Any) -> Any:
    length = _n_items(self)
    if isinstance(key, slice):
        return [_item_at(self, i) for i in range(*key.indices(length))]
    if isinstance(key, int):
        return _item_at(self, _normalize_index(key, length))
    raise TypeError(
        f"list store indices must be integers or slices, not {type(key).__name__}"
    )


@overlay.method("ListModel")
def __iter__(self: Any) -> Iterator[Any]:
    for index in range(_n_items(self)):
        yield _item_at(self, index)


@overlay.method("ListModel", name="__class_getitem__", as_classmethod=True)
def list_model_class_getitem(cls: type[Any], _item: object) -> type[Any]:
    return cls


@overlay.method("ListStore")
def __contains__(self: Any, item: Any) -> bool:
    if not isinstance(item, private.GObject) or not item.is_bound():
        raise TypeError("list store membership test requires a GObject")
    found, _position = self.find(item)
    return bool(found)


@overlay.method("ActionGroup", name="__len__")
def action_group_len(self: Any) -> int:
    return len(self.list_actions())


@overlay.method("ActionGroup", name="__iter__")
def action_group_iter(self: Any) -> Iterator[str]:
    yield from self.list_actions()


@overlay.method("ActionGroup", name="__contains__")
def action_group_contains(self: Any, action_name: object) -> bool:
    if not isinstance(action_name, str):
        return False
    return bool(self.has_action(action_name))


@overlay.method("ListStore")
def __delitem__(self: Any, key: Any) -> None:
    length = _n_items(self)
    if isinstance(key, slice):
        start, stop, step = key.indices(length)
        indices = range(start, stop, step)
        if not indices:
            return
        if step == 1:
            self.splice(start, len(indices), [])
        elif step == -1:
            self.splice(stop + 1, len(indices), [])
        else:
            for i in sorted(indices, reverse=True):
                self.remove(i)
        return
    if isinstance(key, int):
        self.remove(_normalize_index(key, length))
        return
    raise TypeError(
        f"list store indices must be integers or slices, not {type(key).__name__}"
    )


def _validate_list_store_item(store: Any, item: Any) -> None:
    from ginext import GObject as _GObjectNS

    if not isinstance(item, private.GObject):
        raise TypeError(
            f"Expected a GObject, got {type(item).__name__!r}"
        )
    item_type = store.get_item_type()
    item_gtype = getattr(getattr(type(item), "gimeta", None), "gtype", None)
    if item_gtype is None or not _GObjectNS.type_is_a(item_gtype, item_type):
        raise TypeError(
            f"Expected a {_GObjectNS.type_name(item_type)!r}, got {type(item).__name__!r}"
        )


@overlay.method("ListStore")
def __setitem__(self: Any, key: Any, value: Any) -> None:
    if isinstance(key, slice):
        length = _n_items(self)
        indices = range(*key.indices(length))
        items = list(value)
        if key.step is None or key.step == 1:
            for item in items:
                _validate_list_store_item(self, item)
            pos = indices.start
            n_remove = len(indices)
            self.splice(pos, n_remove, items)
        else:
            if len(items) != len(indices):
                raise ValueError(
                    f"attempt to assign sequence of size {len(items)} "
                    f"to extended slice of size {len(indices)}"
                )
            for item in items:
                _validate_list_store_item(self, item)
            for idx, item in zip(indices, items):
                self.splice(idx, 1, [item])
        return
    if not isinstance(key, int):
        raise TypeError(
            f"list store indices must be integers, not {type(key).__name__}"
        )
    length = _n_items(self)
    _validate_list_store_item(self, value)
    self.splice(_normalize_index(key, length), 1, [value])


@overlay.method("ListStore")
def sort(self: Any, compare_func: Any, *user_data: Any) -> None:
    import functools

    items = list(self)

    def _key(item: Any) -> Any:
        return functools.cmp_to_key(lambda a, b: compare_func(a, b, *user_data))(item)

    items.sort(key=_key)
    self.splice(0, _n_items(self), items)


@overlay.method("ListStore")
def insert_sorted(self: Any, item: Any, compare_func: Any, *user_data: Any) -> int:
    import bisect
    import functools

    items = list(self)
    key_fn = functools.cmp_to_key(lambda a, b: compare_func(a, b, *user_data))
    keys = [key_fn(x) for x in items]
    item_key = key_fn(item)
    position = bisect.bisect_right(keys, item_key)
    self.splice(position, 0, [item])
    return position


@overlay.method("ListStore")
def find_with_equal_func(self: Any, item: Any, equal_func: Any, *user_data: Any) -> tuple[bool, int]:
    for i, stored in enumerate(self):
        if equal_func(stored, item, *user_data):
            return True, i
    return False, 2**32 - 1


_OMITTED = object()


@overlay.method("Task", name="new", staticmethod=True)
def _task_new(
    fn: Any,
    source_object: Any,
    cancellable: Any,
    callback: Any,
    callback_data: Any = _OMITTED,
) -> Any:
    if callback_data is _OMITTED:
        return fn(source_object, cancellable, callback)
    return fn(source_object, cancellable, callback, callback_data)


def _settings_schema_for(schema_id: str) -> Any:
    for source in _settings_schema_sources():
        schema = source.lookup(schema_id, True)
        if schema is not None:
            return schema
    return None


def _settings_schema_sources() -> list[Any]:
    sources: list[Any] = []
    default_source = Gio.SettingsSchemaSource.get_default()
    if default_source is not None:
        sources.append(default_source)
    schema_dir = os.environ.get("GSETTINGS_SCHEMA_DIR")
    if not schema_dir:
        return sources

    for directory in schema_dir.split(os.pathsep):
        if not directory:
            continue
        source = Gio.SettingsSchemaSource.new_from_directory(
            directory, default_source, False
        )
        if source is not None:
            sources.append(source)
    return sources


def _settings_list_schemas(*, relocatable: bool) -> list[str]:
    names: set[str] = set()
    for source in _settings_schema_sources():
        non_relocatable, relocatable_names = source.list_schemas(True)
        names.update(relocatable_names if relocatable else non_relocatable)
    return sorted(names)


@overlay.method("Settings", staticmethod=True)
def new(fn: Any, schema_id: str) -> Any:
    schema = _settings_schema_for(schema_id)
    if schema is None:
        raise RuntimeError(f"Settings schema {schema_id!r} is not installed")
    return Gio.Settings.new_full(schema, None, None)


@overlay.method("Settings", staticmethod=True)
def new_with_path(fn: Any, schema_id: str, path: str) -> Any:
    schema = _settings_schema_for(schema_id)
    if schema is None:
        raise RuntimeError(f"Settings schema {schema_id!r} is not installed")
    return Gio.Settings.new_full(schema, None, path)


@overlay.method("Settings", staticmethod=True)
def new_with_backend(fn: Any, schema_id: str, backend: Any) -> Any:
    schema = _settings_schema_for(schema_id)
    if schema is None:
        raise RuntimeError(f"Settings schema {schema_id!r} is not installed")
    return Gio.Settings.new_full(schema, backend, None)


@overlay.method("Settings", staticmethod=True)
def list_schemas(fn: Any) -> list[str]:
    return _settings_list_schemas(relocatable=False)


@overlay.method("Settings", staticmethod=True)
def list_relocatable_schemas(fn: Any) -> list[str]:
    return _settings_list_schemas(relocatable=True)


@overlay.method("FileEnumerator")  # type: ignore[no-redef]
def __iter__(self: Any) -> Any:
    return self


@overlay.method("FileEnumerator")
def __next__(self: Any) -> Any:
    file_info = self.next_file(None)
    if file_info is not None:
        return file_info
    raise StopIteration


class _AsyncFileInfos:
    """async iterator over a FileEnumerator, fetching FileInfo in batches via
    next_files_async / next_files_finish."""

    def __init__(self, enumerator: Any, batch_size: int = 16) -> None:
        self._enumerator = enumerator
        self._batch_size = batch_size
        self._buffer: list[Any] = []
        self._index = 0
        self._done = False

    def __aiter__(self) -> _AsyncFileInfos:
        return self

    async def __anext__(self) -> Any:
        from ginext.aio import _AsyncOperation

        if self._index >= len(self._buffer):
            if self._done:
                raise StopAsyncIteration
            self._buffer = cast(
                "list[Any]",
                await _AsyncOperation(
                    lambda callback: self._enumerator.next_files_async(
                        self._batch_size, 0, None, callback
                    ),
                    lambda result: self._enumerator.next_files_finish(
                        cast("Any", result)
                    ),
                ),
            )
            self._index = 0
            if not self._buffer:
                self._done = True
                raise StopAsyncIteration
        info = self._buffer[self._index]
        self._index += 1
        return info


@overlay.method("FileEnumerator")
def __aiter__(self: Any) -> _AsyncFileInfos:
    return _AsyncFileInfos(self)


def _action_map_add_action(action_map: Any, action: Any) -> None:
    Gio.ActionMap.add_action(action_map, action)


def _process_action_entry(
    action_map: Any,
    name: str,
    activate: Any = None,
    parameter_type: str | None = None,
    state: Any = None,
    change_state: Any = None,
    user_data: Any = None,
) -> None:
    from ginext import GLib
    from ginext.signal.adapt import _SIGNAL_ARG_LIMIT_ATTR, _accepted_signal_arg_count
    from ginext.signal.scoped import static_owner

    def needs_user_data_adapter(callback: Any, signal_arg_count: int) -> bool:
        if user_data is not None:
            return True
        accepted = _accepted_signal_arg_count(callback)
        return accepted is not None and accepted > signal_arg_count

    def with_user_data(callback: Any) -> Any:
        signal_arg_limit = _accepted_signal_arg_count(callback, 1)

        def adapter(*signal_args: Any) -> Any:
            return callback(*signal_args, user_data)

        setattr(adapter, _SIGNAL_ARG_LIMIT_ATTR, signal_arg_limit)
        return adapter

    if parameter_type:
        if not GLib.VariantType.string_is_valid(parameter_type):
            raise TypeError(
                f"The type string {parameter_type!r} given as the parameter type "
                f"for action {name!r} is not a valid GVariant type string."
            )
        variant_parameter = GLib.VariantType.new(parameter_type)
    else:
        variant_parameter = None

    if state is not None:
        variant_state = GLib.Variant.parse(None, state, None, None)
        action = Gio.SimpleAction.new_stateful(name, variant_parameter, variant_state)
        if change_state is not None:
            if needs_user_data_adapter(change_state, 2):
                change_state = with_user_data(change_state)
            change_state_signal: Any = action.change_state
            change_state_signal.connect(change_state, owner=static_owner)
    else:
        if change_state is not None:
            raise ValueError(
                f"Stateless action {name!r} should give None for "
                f"'change_state', not {change_state!r}."
            )
        action = Gio.SimpleAction.new(name, variant_parameter)

    if activate is not None:
        if needs_user_data_adapter(activate, 2):
            activate = with_user_data(activate)
        activate_signal: Any = action.activate
        activate_signal.connect(activate, owner=static_owner)
    _action_map_add_action(action_map, action)


def _add_action_entries(self: Any, entries: Any, user_data: Any = None) -> None:
    try:
        iter(entries)
    except TypeError:
        raise TypeError("entries must be iterable") from None
    for entry in entries:
        _process_action_entry(self, *entry, user_data=user_data)  # type: ignore[misc]


_add_action_entries.__name__ = "add_action_entries"

for _cls in ("Application", "SimpleActionGroup"):
    overlay.method(_cls)(_add_action_entries)


def _lookup_action(self: Any, action_name: str) -> Any:
    return private.invoke(
        "Gio",
        "ActionMap.lookup_action",
        self,
        action_name,
    )


_lookup_action.__name__ = "lookup_action"

for _cls in ("Application", "SimpleActionGroup"):
    overlay.method(_cls)(_lookup_action)


@overlay.method("VolumeMonitor")
def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
    import warnings
    from ginext import PyGIWarning

    super(Gio.VolumeMonitor, self).__init__(*args, **kwargs)
    warnings.warn(
        "Gio.VolumeMonitor shouldn't be instantiated directly, "
        "use Gio.VolumeMonitor.get() instead.",
        PyGIWarning,
        stacklevel=2,
    )


@overlay.method("SimpleAction")
def get_name(self: Any) -> str:
    return str(Gio.Action.get_name(self))


@overlay.method("Settings")  # type: ignore[no-redef]
def __contains__(self: Any, key: Any) -> bool:
    return bool(key in self.list_keys())


@overlay.method("Settings")  # type: ignore[no-redef]
def __len__(self: Any) -> int:
    return int(len(self.list_keys()))


@overlay.method("Settings")  # type: ignore[no-redef]
def __iter__(self: Any) -> Iterator[Any]:
    return iter(self.list_keys())


@overlay.method("Settings")  # type: ignore[no-redef]
def __bool__(self: Any) -> bool:
    return True


@overlay.method("Settings")  # type: ignore[no-redef]
def __getitem__(self: Any, key: Any) -> Any:
    if key not in self:
        raise KeyError(f"unknown key: {key!r}")
    return self.get_value(key).unpack()


@overlay.method("Settings")  # type: ignore[no-redef]
def __setitem__(self: Any, key: Any, value: Any) -> None:
    from ginext import GLib

    if key not in self:
        raise KeyError(f"unknown key: {key!r}")
    range_ = self.get_range(key)
    type_ = range_.get_child_value(0).get_string()
    v = range_.get_child_value(1)
    if type_ == "type":
        type_str = v.get_child_value(0).get_type_string()
        assert type_str.startswith("a")
        type_str = type_str[1:]
    elif type_ == "enum":
        assert v.get_child_value(0).get_type_string().startswith("a")
        type_str = v.get_child_value(0).get_child_value(0).get_type_string()
        allowed = v.unpack()
        if value not in allowed:
            raise ValueError(f"value {value} is not an allowed enum ({allowed})")
    elif type_ == "range":
        tuple_ = v.get_child_value(0)
        type_str = tuple_.get_child_value(0).get_type_string()
        min_, max_ = tuple_.unpack()
        if value < min_ or value > max_:
            raise ValueError(f"value {value} not in range ({min_} - {max_})")
    else:
        raise NotImplementedError(
            "Cannot handle allowed type range class " + str(type_)
        )
    self.set_value(key, GLib.Variant(type_str, value))


@overlay.method("Settings")
def keys(self: Any) -> Any:
    return self.list_keys()


@overlay.method("Cancellable")
def __enter__(self: Any) -> Any:
    # A cancel scope: the cancellable is the current one inside the block and
    # is cancelled when the block exits (cleanly or by exception), so work
    # tied to it stops. push/pop_current is GIO's own ambient-cancellable
    # stack; nesting restores the enclosing scope.
    self.push_current()
    return self


@overlay.method("Cancellable")
def __exit__(
    self: Any, exc_type: Any, exc_value: Any, traceback: Any
) -> Literal[False]:
    self.pop_current()
    self.cancel()
    return False


@overlay.method("File")
def __fspath__(self: Any) -> str:
    path = self.peek_path()
    if path is None:
        raise TypeError(f"Gio.File at {self.get_uri()!r} is not backed by a local path")
    return str(path)


@overlay.method("File")
def __truediv__(self: Any, other: Any) -> Any:
    import os as _os

    if isinstance(other, bytes):
        other = _os.fsdecode(other)
    if not isinstance(other, str):
        raise TypeError(
            f"unsupported operand type(s) for /: 'File' and {type(other).__name__!r}"
        )
    return self.resolve_relative_path(other)


@overlay.method("MenuItem")
def set_attribute(
    self: Any, attribute: Any, format_string: Any = None, *args: Any
) -> None:
    from ginext import GLib

    if isinstance(attribute, list):
        for entry in attribute:
            attr, fmt, *vals = entry
            self.set_attribute(attr, fmt, *vals)
    elif format_string is None:
        self.set_attribute_value(attribute, None)
    else:
        value = GLib.Variant(format_string, args[0] if len(args) == 1 else tuple(args))
        self.set_attribute_value(attribute, value)


def _menu_item_at(model: Any, index: int) -> Any:
    return Gio.MenuItem.new_from_model(model, index)


@overlay.method("MenuModel", name="__len__")
def menu_model_len(self: Any) -> int:
    return int(self.get_n_items())


@overlay.method("MenuModel", name="__getitem__")
def menu_model_getitem(self: Any, key: object) -> Any:
    length = len(self)
    match key:
        case slice():
            return [_menu_item_at(self, i) for i in range(*key.indices(length))]
        case int():
            return _menu_item_at(self, _normalize_position(key, length))
        case _:
            raise TypeError(
                "menu model indices must be integers or slices, not "
                f"{type(key).__name__}"
            )


@overlay.method("MenuModel", name="__iter__")
def menu_model_iter(self: Any) -> Iterator[Any]:
    for index in range(len(self)):
        yield _menu_item_at(self, index)


# ── D-Bus ─────────────────────────────────────────────────────────────────────


@overlay.replace
def bus_get(fn: Any, bus_type: Any, cancellable: Any = None) -> Any:
    from ginext.aio import _AsyncOperation

    return _AsyncOperation(
        lambda cb: fn(bus_type, cancellable, cb),
        lambda r: Gio.bus_get_finish(cast("Any", r)),
    )


def _unpack_dbus_result(variant: Any) -> Any:
    result = variant.unpack()
    if len(result) == 1:
        return result[0]
    if len(result) == 0:
        return None
    return result


class _DBusProxyMethodCall:
    __slots__ = ("_proxy", "_method_name")

    def __init__(self, proxy: Any, method_name: str) -> None:
        self._proxy = proxy
        self._method_name = method_name

    def __call__(self, *args: Any, flags: int = 0, timeout: int = -1) -> Any:
        from ginext.aio import _AsyncOperation

        if args and isinstance(args[0], str):
            signature, rest = args[0], args[1:]
            from ginext import GLib

            arg_variant = GLib.Variant(signature, tuple(rest))
        else:
            arg_variant = None

        proxy = self._proxy
        method = self._method_name
        return _AsyncOperation(
            lambda cb: proxy.call(method, arg_variant, flags, timeout, None, cb),
            lambda r: _unpack_dbus_result(proxy.call_finish(r)),
        )


# Defined as a named function (not a literal module-level ``def __getattr__``)
# so it does not become this module's PEP 562 ``__getattr__`` hook, which would
# hijack every ``getattr(module, ...)`` probe (e.g. unittest.assertWarns
# scanning sys.modules for ``__warningregistry__``).
def _dbus_proxy_getattr(self: Any, name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    from ginext.classbuild import method_for_instance

    method = method_for_instance(self, name)
    if method is not None:
        return method
    return _DBusProxyMethodCall(self, name)


_dbus_proxy_getattr.__name__ = "__getattr__"
overlay.method("DBusProxy")(_dbus_proxy_getattr)


@overlay.method("DBusProxy")  # type: ignore[no-redef]
def __getitem__(self: Any, key: Any) -> Any:
    v = self.get_cached_property(key)
    if v is None:
        raise KeyError(key)
    return v.unpack()


@overlay.method("DBusProxy", staticmethod=True)
def new_for_bus(
    fn: Any,
    bus_type: Any,
    flags: Any,
    info: Any,
    name: Any,
    object_path: Any,
    interface_name: Any,
    cancellable: Any = None,
) -> Any:
    from ginext.aio import _AsyncOperation

    return _AsyncOperation(
        lambda cb: fn(
            bus_type, flags, info, name, object_path, interface_name, cancellable, cb
        ),
        lambda r: Gio.DBusProxy.new_for_bus_finish(cast("Any", r)),
    )


class _SignalSubscription:
    __slots__ = ("_conn", "_id")

    def __init__(self, conn: Any, subscription_id: Any) -> None:
        self._conn = conn
        self._id = subscription_id

    @property
    def subscription_id(self) -> Any:
        return self._id

    def cancel(self) -> None:
        if self._id is not None:
            self._conn.signal_unsubscribe(self._id)
            self._id = None

    def __enter__(self) -> _SignalSubscription:
        return self

    def __exit__(self, *_: Any) -> None:
        self.cancel()


@overlay.method("DBusConnection")
def signal_subscribe(
    fn: Any,
    self: Any,
    sender: Any,
    interface_name: Any,
    member: Any,
    object_path: Any,
    callback: Any,
    *,
    arg0: Any = None,
    flags: int = 0,
) -> _SignalSubscription:
    # GI strips user_data from GLib callbacks, so pass callback directly.
    # callback receives (conn, sender, object_path, interface_name, signal, params).
    sub_id = fn(
        self,
        sender,
        interface_name,
        member,
        object_path,
        arg0,
        flags,
        callback,
    )
    return _SignalSubscription(self, sub_id)


class _ObjectRegistration:
    __slots__ = ("_conn", "_id")

    def __init__(self, conn: Any, registration_id: Any) -> None:
        self._conn = conn
        self._id = registration_id

    def cancel(self) -> None:
        if self._id is not None:
            self._conn.unregister_object(self._id)
            self._id = None

    def __enter__(self) -> _ObjectRegistration:
        return self

    def __exit__(self, *_: Any) -> None:
        self.cancel()


def _NOOP(*_a: Any) -> None:
    pass


@overlay.method("DBusConnection")
def register_object(
    self: Any,
    object_path: Any,
    interface_info: Any,
    method_call_fn: Any = None,
    get_property_fn: Any = None,
    set_property_fn: Any = None,
) -> _ObjectRegistration:
    reg_id = self.register_object_with_closures2(
        object_path,
        interface_info,
        method_call_fn if method_call_fn is not None else _NOOP,
        get_property_fn if get_property_fn is not None else _NOOP,
        set_property_fn if set_property_fn is not None else _NOOP,
    )
    return _ObjectRegistration(self, reg_id)
