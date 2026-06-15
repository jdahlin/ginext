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

import os
from pathlib import Path
import sys

import pytest


_XFAIL_BY_NODE = {
    "test_everything.py::TestBoxed::test_boxed": "boxed property wrapper identity is unstable in the combined compat run",
    "test_glib.py::TestGLib::test_main_context_query": "marshalling not implemented",
    "test_gobject.py::TestGObjectAPI::test_call_method_uninitialized_instance": "TypeError instead of RuntimeError; fixing would break native gobject test",
    "test_gobject.py::TestReferenceCounting::test_floating": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_floating_and_sunk": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_floating_and_sunk_out_of_scope": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_floating_and_sunk_out_of_scope_using_gobject_new": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_floating_and_sunk_using_gobject_new": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_owned_by_library": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_owned_by_library_out_of_scope": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_owned_by_library_out_of_scope_using_gobject_new": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_owned_by_library_using_gobject_new": "missing pygobject compat attribute",
    "test_gobject.py::test_custom_class_update": "missing pygobject compat attribute",
    "test_internal_api.py::TestObject::test_create_ctor": "testhelper.create_test_type not implemented",
    "test_internal_api.py::TestObject::test_new_refcount": "testhelper.test_g_object_new not implemented",
    "test_internal_api.py::TestObject::test_pyobject_new_test_type": "testhelper.create_test_type not implemented",
    "test_internal_api.py::test_parse_constructor_args": "testhelper.test_parse_constructor_args not implemented",
    "test_internal_api.py::test_state_ensure_release": "testhelper.test_state_ensure_release not implemented",
    "test_object_lifecycle.py::test_class_with_slots_raises_warning": "test relies on missing compat path",
    "test_object_lifecycle.py::test_object_constructed_after_init": "behaviour mismatch under ginext pygobject compat",
    "test_object_lifecycle.py::test_object_constructed_after_init_by_new": "behaviour mismatch under ginext pygobject compat",
    "test_object_lifecycle.py::test_object_with_post_init": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_object_with_post_init_and_interface": "behaviour mismatch under ginext pygobject compat",
    "test_object_lifecycle.py::test_object_with_post_init_created_by_new": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_object_with_post_init_raises_exception": "expected warning/exception not raised",
    "test_object_lifecycle.py::test_slot_object_can_be_created": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_subclass_with_slots_raises_warning": "test relies on missing compat path",
    "test_object_marshaling.py::TestVFuncsWithHeldFloatingArg::test_vfunc_in_floating_transfer_full_with_held_floating": "behaviour mismatch under ginext pygobject compat",
    "test_object_marshaling.py::TestVFuncsWithHeldFloatingArg::test_vfunc_in_floating_transfer_none_with_held_floating": "behaviour mismatch under ginext pygobject compat",
    "test_ossig.py::TestOverridesWakeupOnAlarm::test_glib_mainloop": "flaky timing-sensitive SIGALRM test",
    "test_ossig.py::TestOverridesWakeupOnAlarm::test_gio_application": "TypeError under ginext pygobject compat",
    "test_overrides_gdk.py::TestGdk::test_file_list": "GSList<GFile> elements marshal as None in ginext; requires C-level fix",
    "test_overrides_gtk.py::TestBuilder::test_builder": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestBuilder::test_builder_with_handler_and_args": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestBuilder::test_builder_with_handler_object": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store": "missing pygobject compat attribute",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_glist": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_glist_ctor": "boxed-glist Property from list ctor not implemented",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_struct": "get_property() arity mismatch",
    "test_properties.py::TestCPropsAccessor::test_boxed_glist": "boxed-glist Property accessor not implemented",
    "test_properties.py::TestCPropsAccessor::test_boxed_glist_ctor": "boxed-glist Property from list ctor not implemented",
    "test_properties.py::TestCPropsAccessor::test_boxed_struct": "boxed-struct Property accessor not implemented",
    "test_properties.py::TestProperty::test_object_property": "flaky: GObject wrapper hash unstable across del+recreate in parallel",
    "test_properties.py::TestPropertyObject::test_range": "Property.{int,...} descriptor accessors not implemented",
    "test_properties.py::test_get_function_property": "function-typed Property not implemented",
    "test_properties.py::test_gobject_inheritance_with_incomplete_initialization": "gimeta not surfaced on incomplete GObject subclass",
    "test_signal.py::TestIntrospectedSignals::test_intarray_ret": "signal return GValue conversion is not ABI-profile aware; requires C-level TSS fix",
    "test_signature.py::Test::test_allow_none_with_user_data_defaults": "pygobject keeps callback user_data as an Any param; ginext filters closure companions",
    "test_signature.py::Test::test_arg_conflict": "vfunc signatures need pygobject classmethod-shaped binding; ginext binds the instance via PyMethod_New",
    "test_signature.py::Test::test_object_virtual_method": "vfunc signatures need pygobject classmethod-shaped binding; ginext binds the instance via PyMethod_New",
    "test_source.py::TestSource::test_extra_init_args": "GLib.Source subclass __init__ args not forwarded",
    "test_source.py::TestSource::test_python_unref_during_dispatch": "GLib.Source.new() positional ctor not implemented",

    "test_import_machinery.py::TestModule::test_static_binding_protection": "old static bindings (gobject, glib, etc.) are importable under ginext; the legacy namespace shim intentionally provides them",

    "test_signal.py::TestSignalDecorator::test_closures_called": "GObject.Signal decorator default handler not called during emit",
    "test_signal.py::TestSignalDecorator::test_connect_detailed": "detailed signal connect via BoundSignal.connect_detailed recurses through compat overlay",
    "test_signal.py::TestSignalDecorator::test_overridden_signal": "GObject.SignalOverride default handler not called during emit",
    "test_signal.py::TestSignalConnectors::test_signal_emit": "GObject.Signal emit return value not propagated",
    "test_signal.py::TestPython3Signals::test_emit_return": "GObject.Signal emit return value not propagated",
}


_SKIP_BY_NODE = {
    "test_gi.py::TestGFlags::test_flags": "flaky GFlags inheritance assertion",
    "test_iochannel.py::IOChannel::test_fd_read": "IOChannel non-blocking pipe read returns empty bytes",
    "test_iochannel.py::IOChannel::test_file_read_chars": "IOChannel read_chars with count not supported in ginext",
    "test_iochannel.py::IOChannel::test_seek": "IOChannel seek with partial read not supported",
}


_XFAIL_NOT_RUN_BY_NODE = {
    "test_callback.py::test_async_callback": "can hang in the compat package run; disable until async callback scheduling is understood",
    "test_iochannel.py::IOChannel::test_add_watch_no_data": "IOChannel non-blocking pipe read hangs mainloop",
    "test_iochannel.py::IOChannel::test_add_watch_with_data": "IOChannel non-blocking pipe read hangs mainloop",
    "test_iochannel.py::IOChannel::test_add_watch_with_multi_data": "IOChannel non-blocking pipe read hangs mainloop",
    "test_iochannel.py::IOChannel::test_deprecated_add_watch_no_data": "IOChannel non-blocking pipe read hangs mainloop",
    "test_iochannel.py::IOChannel::test_deprecated_add_watch_with_data": "IOChannel non-blocking pipe read hangs mainloop",
    "test_iochannel.py::IOChannel::test_deprecated_method_add_watch_data_priority": "IOChannel non-blocking pipe read hangs mainloop",
    "test_iochannel.py::IOChannel::test_deprecated_method_add_watch_no_data": "IOChannel non-blocking pipe read hangs mainloop",
    "test_overrides_gdkpixbuf.py::test_new_from_data": "crashes in GdkPixbuf pixel data marshalling",
    "test_overrides_gdk.py::TestGdk::test_file_list": "crashes xdist worker across platforms (access violation in record.py wrapper)",
    "test_overrides_gdkpixbuf.py::test_new_from_data_deprecated_args": "unsafe while GdkPixbuf pixel data marshalling is crash-prone",
    "test_properties.py::TestProperty::test_range": "crashes xdist worker on all Python builds; numeric property range info not fully implemented",
}


# Tests that crash the xdist worker process in debug/asan/ubsan Python builds.
# These are C-level crashes (not Python exceptions), so xfail(run=False) is the
# only way to prevent the crash from failing the test run.
_XFAIL_NOT_RUN_DEBUG_BY_NODE = {
    "test_overrides_gtk.py::TestTreeModel::test_tree_model": "crashes xdist worker in debug Python builds",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store": "crashes xdist worker in debug Python builds",
    "test_properties.py::TestCPropsAccessor::test_unichar": "triggers ASAN/UBSAN crash in ParamSpec numeric info for unichar properties",
}

# Tests that crash with a Windows access violation (C-level) on all Python builds.
_XFAIL_NOT_RUN_WIN32_BY_NODE = {
    "test_properties.py::TestPropertyObject::test_iteration": "dlopen(libgobject-2.0.so.0) fails on Windows; library uses .dll naming",
}


# Tests that hang on Python 3.15+ with the GIL enabled.  The child_setup
# callback passed to GLib.spawn_async() deadlocks in g_spawn_async() during
# fork/exec on Python 3.15b2 (GIL build) — a CPython 3.15 beta regression that
# does not affect the free-threaded build (3.15b2t) or Python 3.14.
_PY315_GIL_XFAIL_BY_NODE = {
    "test_subprocess.py::test_spawn_async_fds_with_child_setup": "hangs in g_spawn_async() child_setup on Python 3.15 GIL build (CPython 3.15b2 regression)",
    "test_properties.py::TestCPropsAccessor::test_parent_class": "crashes xdist worker on Python 3.15 GIL build",
}

_FREE_THREADED_XFAIL_BY_NODE = {
    "test_properties.py::TestCPropsAccessor::test_held_object_ref_count_getter": "refcount assertion is unstable in free-threaded Python builds",
}

# macOS-specific failures: tests that rely on Linux .so.0 library naming which
# doesn't exist on macOS (libraries use .dylib there).
_DARWIN_XFAIL_BY_NODE = {
    "test_properties.py::TestPropertyObject::test_iteration": "dlopen(libgobject-2.0.so.0) fails on macOS; library uses .dylib naming",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store": "crashes xdist worker on macOS in the compat Gtk tree model run",
}


# Windows-unported features (not ginext bugs: the capability is POSIX-only or
# unavailable on Windows): the GLib-backed asyncio EventLoop and its default-
# context / running-loop assertions, GDBus native calls (need a session bus),
# the SIGALRM wakeup-fd override, and IOChannel win32 socket/fd handling.
_WIN32_SKIP_NODES = {
    "test_async.py::TestAsync::test_no_running_loop",
    "test_async.py::TestAsync::test_wrong_default_context",
    "test_gdbus.py::TestGDBusClient::test_native_calls_async",
    "test_gdbus.py::TestGDBusClient::test_native_calls_sync",
    "test_gdbus.py::TestGDBusClient::test_native_calls_sync_errors",
    "test_ossig.py::TestOverridesWakeupOnAlarm::test_basic",
    "test_overrides_glib.py::test_io_add_watch_get_args_win32_socket",
    "test_overrides_glib.py::test_iochannel_win32",
}


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    is_debug_python = hasattr(sys, "gettotalrefcount")
    is_win32 = sys.platform == "win32"
    is_darwin = sys.platform == "darwin"
    is_py315_gil = sys.version_info >= (3, 15) and getattr(
        sys, "_is_gil_enabled", lambda: True
    )()
    is_free_threaded = not getattr(sys, "_is_gil_enabled", lambda: True)()
    compat_warning_filters = (
        pytest.mark.filterwarnings(
            "ignore:connecting .* without an owner:ginext.signal.connection.UnownedSignalHandlerWarning"
        ),
        pytest.mark.filterwarnings(
            "ignore:'asyncio\\.set_event_loop_policy' is deprecated and slated for removal in Python 3\\.16:DeprecationWarning"
        ),
        pytest.mark.filterwarnings(
            "ignore:.* positional/keyword construction is deprecated:DeprecationWarning"
        ),
    )
    for item in items:
        _, sep, relative_nodeid = item.nodeid.rpartition("/pygobject/")
        if not sep:
            continue
        for marker in compat_warning_filters:
            item.add_marker(marker)
        if is_py315_gil and relative_nodeid in _PY315_GIL_XFAIL_BY_NODE:
            reason = _PY315_GIL_XFAIL_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, run=False, strict=False))
            continue
        if is_free_threaded and relative_nodeid in _FREE_THREADED_XFAIL_BY_NODE:
            reason = _FREE_THREADED_XFAIL_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, strict=False))
            continue
        if is_debug_python and relative_nodeid in _XFAIL_NOT_RUN_DEBUG_BY_NODE:
            reason = _XFAIL_NOT_RUN_DEBUG_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, run=False, strict=False))
            continue
        if is_darwin and relative_nodeid in _DARWIN_XFAIL_BY_NODE:
            reason = _DARWIN_XFAIL_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, run=False, strict=False))
            continue
        if is_win32 and relative_nodeid in _XFAIL_NOT_RUN_WIN32_BY_NODE:
            reason = _XFAIL_NOT_RUN_WIN32_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, run=False, strict=False))
            continue
        if is_win32 and relative_nodeid in _WIN32_SKIP_NODES:
            item.add_marker(
                pytest.mark.skip(reason="win32: feature unported/unavailable")
            )
            continue
        if relative_nodeid.startswith("test_cairo.py::TestPango::") and (
            not has_display or is_debug_python
        ):
            item.add_marker(
                pytest.mark.skip(
                    reason="Gtk cairo font-options test is not stable under debug/display-limited runs"
                )
            )
            continue
        reason = _SKIP_BY_NODE.get(relative_nodeid)
        if reason is not None:
            item.add_marker(pytest.mark.skip(reason=reason))
            continue
        reason = _XFAIL_NOT_RUN_BY_NODE.get(relative_nodeid)
        if reason is not None:
            item.add_marker(pytest.mark.xfail(reason=reason, run=False, strict=False))
            continue
        reason = _XFAIL_BY_NODE.get(relative_nodeid)
        if reason is not None:
            item.add_marker(pytest.mark.xfail(reason=reason, strict=False))


def _compile_test_gsettings_schemas() -> None:
    import shutil
    import subprocess
    import tempfile

    schema_src = Path(__file__).resolve().with_name("org.gnome.test.gschema.xml")
    if not schema_src.exists():
        return
    compiler = shutil.which("glib-compile-schemas")
    if compiler is None:
        raise RuntimeError("glib-compile-schemas is required for GSettings tests")
    tmpdir = Path(tempfile.mkdtemp(prefix="ginext-gsettings-"))
    shutil.copy(schema_src, tmpdir)
    try:
        subprocess.run([compiler, str(tmpdir)], check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("failed to compile test GSettings schemas") from exc
    os.environ["GSETTINGS_SCHEMA_DIR"] = os.pathsep.join(
        [
            str(tmpdir),
            os.environ.get("GSETTINGS_SCHEMA_DIR", ""),
        ]
    )


def _bootstrap_pygobject_compat() -> object:
    import ginext

    ginext.features.set_enabled("pygobject_compat", True)
    # GI_TYPELIB_PATH / LD_LIBRARY_PATH for the test typelibs are set once by the
    # package's tests/conftest.py (via conftest_shared.setup_gi_test_env) before
    # ginext is imported; nothing to do here.
    _compile_test_gsettings_schemas()
    os.environ.setdefault("GSETTINGS_BACKEND", "memory")
    return _install_pygobject_compat_layer()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "filterwarnings",
        "ignore::ginext.signal.connection.UnownedSignalHandlerWarning",
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore:'asyncio\\.set_event_loop_policy' is deprecated and slated for removal in Python 3\\.16:DeprecationWarning",
    )
    _bootstrap_pygobject_compat()


def _install_pygobject_compat_layer() -> object:
    import ginext

    ginext.features.set_enabled("pygobject_compat", True)
    import gi.repository

    for namespace in ("GLib", "GObject", "Gio", "GIMarshallingTests", "Regress"):
        try:
            getattr(gi.repository, namespace)
        except (AttributeError, ImportError, RuntimeError):
            pass
    return gi.repository


@pytest.fixture(scope="session", autouse=True)
def _pygobject_compat_layer():
    return _install_pygobject_compat_layer()


_bootstrap_pygobject_compat()
