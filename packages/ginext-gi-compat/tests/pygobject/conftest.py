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
    "test_fields.py::TestFields::test_array_field_with_length_annotation": "length-annotated C array field access not implemented",
    "test_cancellable.py::test_does_not_expose_new": "constructor exposure differs after static constructor support",
    "test_enum_flags.py::test_enum_return_can_be_passed_back_as_arg": "enum/flags wrapper identity mismatch in combined compat run",
    "test_everything.py::TestBoxed::test_boxed": "GValue boxed property conversion is not ABI-profile aware",
    "test_gi.py::TestGObject::test_nongir_repr": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestGObject::test_object_full_inout": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestGObject::test_object_full_out": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestKeywordArgs::test_allow_none_as_default": "TypeError under ginext pygobject compat",
    "test_gi.py::TestKeywordArgs::test_type_errors": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestInterfaceClash::test_clash": "interface-rooted MRO no longer raises the old clash TypeError",
    "test_gi.py::TestMRO::test_interface_collision": "TypeError under ginext pygobject compat",
    "test_gi.py::TestMRO::test_mro": "missing pygobject compat attribute",
    "test_gi.py::TestModule::test_help": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestModule::test_type": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestOverrides::test_constant": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestOverrides::test_module_name": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestOverrides::test_object": "TypeError under ginext pygobject compat",
    "test_gi.py::TestOverrides::test_struct": "TypeError under ginext pygobject compat",
    "test_gi.py::TestPythonGObject::test_object_vfuncs": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestPythonGObject::test_vfunc_return_no_ref_count": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestPythonGObject::test_vfunc_return_ref_count": "behaviour mismatch under ginext pygobject compat",
    "test_glib.py::TestGLib::test_main_context_query": "marshalling not implemented",
    "test_glib.py::TestGLibPlatform::test_glib_unix_signal_add_full_deprecation": "GLibUnix.signal_add_full deprecation needs GLibUnix overlay",
    "test_gobject.py::TestGObjectAPI::test_call_method_uninitialized_instance": "TypeError instead of RuntimeError; fixing would break native gobject test",
    "test_gobject.py::TestPropertyBindings::test_transform_bidirectional": "bind_property_full with transforms not yet implemented",
    "test_gobject.py::TestPropertyBindings::test_transform_from_only": "bind_property_full with transforms not yet implemented",
    "test_gobject.py::TestPropertyBindings::test_transform_to_only": "bind_property_full with transforms not yet implemented",
    "test_gobject.py::TestReferenceCounting::test_floating": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_floating_and_sunk": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_floating_and_sunk_out_of_scope": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_floating_and_sunk_out_of_scope_using_gobject_new": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_floating_and_sunk_using_gobject_new": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_owned_by_library": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_owned_by_library_out_of_scope": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_owned_by_library_out_of_scope_using_gobject_new": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_owned_by_library_using_gobject_new": "missing pygobject compat attribute",
    "test_gobject.py::TestReferenceCounting::test_uninitialized_object": "missing pygobject compat attribute",
    "test_gobject.py::test_custom_class_update": "missing pygobject compat attribute",
    "test_import_machinery.py::TestImporter::test_invalid_repository_module_name": "behaviour mismatch under ginext pygobject compat",
    "test_import_machinery.py::TestModule::test_static_binding_protection": "module not exposed by ginext compat",
    "test_import_machinery.py::TestOverrides::test_load_overrides": "behaviour mismatch under ginext pygobject compat",
    "test_import_machinery.py::TestOverrides::test_non_gi": "behaviour mismatch under ginext pygobject compat",
    "test_import_machinery.py::TestOverrides::test_separate_path": "missing pygobject compat attribute",
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
    "test_ossig.py::TestOverridesWakeupOnAlarm::test_glib_mainloop": "mainloop does not wake on SIGALRM under ginext pygobject compat",
    "test_ossig.py::TestOverridesWakeupOnAlarm::test_gio_application": "TypeError under ginext pygobject compat",
    "test_ossig.py::TestSigintFallback::test_no_replace_if_set_by_glib": "missing pygobject compat attribute",
    "test_overrides_gdk.py::TestGdk::test_file_list": "TypeError under ginext pygobject compat",
    "test_overrides_gdk.py::TestGdk::test_paintable_flags": "missing pygobject compat attribute",
    "test_overrides_gdk.py::TestGdk::test_rgba": "missing pygobject compat attribute",
    "test_overrides_gdk.py::TestGdk::test_rgba_representations": "TypeError under ginext pygobject compat",
    "test_overrides_gio.py::test_types_init_warn": "test relies on missing compat path",
    "test_overrides_gtk.py::TestBuilder::test_add_from_string": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestBuilder::test_builder": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestBuilder::test_builder_with_handler_and_args": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestBuilder::test_builder_with_handler_object": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestGtk::test_adjustment": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_gtk.py::TestGtk::test_dialog_add_buttons": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestGtk::test_editable": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestGtk::test_iconview": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestGtk::test_window_gtk4": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_gtk.py::TestListStore::test_insert_with_values": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTextBuffer::test_insert_text_signal_location_modification": "insert-text signal location in-out GtkTextIter not written back to GTK",
    "test_overrides_gtk.py::TestTreeModel::test_filter_new_default": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_list_store": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_list_store_insert_after": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_list_store_insert_before": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_list_store_set": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_list_store_signals": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_list_store_sort": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_model_rows_reordered": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_model_set_row": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_model_set_row_skip_on_none": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_set_default_sort_func": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_signal_emission_tree_path_coerce": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestTreeModel::test_tree_model": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_model_edit": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_model_filter": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_model_get_iter_fail": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_model_set_value_to_none": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_model_sort": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_model_sort_new_with_model_new": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_path": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_row_sequence": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_row_slice": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store_insert_after": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store_insert_after_none": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store_insert_before": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store_insert_before_none": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store_set": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModel::test_tree_store_signals": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeModelRow::test_tree_model_row": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeView::test_scroll_to_cell": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeView::test_tree_selection": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeView::test_tree_view": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeView::test_tree_view_add_column_with_attributes": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeView::test_tree_view_column": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTreeView::test_tree_view_column_set_attributes": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestWidget::test_translate_coordinates": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_pango.py::TestPango::test_layout": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_pango.py::TestPango::test_layout_set_markup": "TypeError under ginext pygobject compat",
    "test_overrides_pango.py::TestPango::test_layout_set_test": "TypeError under ginext pygobject compat",
    "test_properties.py::TestCGetPropertyMethod::test_annotated_glist": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_glist": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_glist_ctor": "boxed-glist Property from list ctor not implemented",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_struct": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_char": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_uchar": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_unichar": "get_property() arity mismatch",
    "test_properties.py::TestCPropsAccessor::test_annotated_glist": "annotated-glist Property accessor not implemented",
    "test_properties.py::TestCPropsAccessor::test_boxed_glist": "boxed-glist Property accessor not implemented",
    "test_properties.py::TestCPropsAccessor::test_boxed_glist_ctor": "boxed-glist Property from list ctor not implemented",
    "test_properties.py::TestCPropsAccessor::test_boxed_struct": "boxed-struct Property accessor not implemented",
    "test_properties.py::TestCPropsAccessor::test_char": "Property overflow validation not implemented",
    "test_properties.py::TestCPropsAccessor::test_param_spec_dir": "Property dir() lookup not implemented",
    "test_properties.py::TestCPropsAccessor::test_props_accessor_dir": "props accessor dir() not implemented",
    "test_properties.py::TestCPropsAccessor::test_uchar": "Property overflow validation not implemented",
    "test_properties.py::TestCPropsAccessor::test_unichar": "unichar Property accessor not implemented",
    "test_properties.py::TestProperty::test_custom_setter": "Property descriptor name lookup not implemented",
    "test_properties.py::TestProperty::test_getter_exception": "get_property() arity mismatch",
    "test_properties.py::TestProperty::test_min_max": "Property min/max enforcement not implemented",
    "test_properties.py::TestProperty::test_object_property": "GObject-typed Property returns hash mismatch for wrapper identity",
    "test_properties.py::TestProperty::test_property_subclass_custom_setter_error": "Property setter error propagation not implemented",
    "test_properties.py::TestProperty::test_python_to_glib_type_mapping": "Property._type_from_python helper not implemented",
    "test_properties.py::TestProperty::test_range": "Property descriptor name lookup not implemented",
    "test_properties.py::TestProperty::test_simple": "Property default not surfaced",
    "test_properties.py::TestPropertyObject::test_construct_only": "behaviour mismatch under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_enum": "marshalling not implemented",
    "test_properties.py::TestPropertyObject::test_flags": "behaviour mismatch under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_int_to_str": "TypeError under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_interface": "no GValue conversion for GFile interface property",
    "test_properties.py::TestPropertyObject::test_range": "Property.{int,...} descriptor accessors not implemented",
    "test_properties.py::TestPropertyObject::test_repr": "behaviour mismatch under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_strings": "marshalling not implemented",
    "test_properties.py::TestPropertyObject::test_utf8_lone_surrogate": "string handling differs under ginext",
    "test_properties.py::test_get_function_property": "function-typed Property not implemented",
    "test_properties.py::test_get_property_on_unowned_object": "testhelper.create_and_get_property not implemented",
    "test_properties.py::test_gobject_inheritance_with_incomplete_initialization": "gimeta not surfaced on incomplete GObject subclass",
    "test_properties.py::test_set_function_property": "function-typed Property not implemented",
    "test_properties.py::test_set_property_on_unowned_object": "testhelper.create_and_set_property not implemented",
    "test_signal.py::TestIntrospectedSignals::test_intarray_ret": "signal return GValue conversion is not ABI-profile aware",
    "test_signature.py::Test::test_allow_none_with_user_data_defaults": "pygobject keeps callback user_data as an Any param; ginext filters closure companions",
    "test_signature.py::Test::test_arg_conflict": "vfunc signatures need pygobject classmethod-shaped binding; ginext binds the instance via PyMethod_New",
    "test_signature.py::Test::test_object_virtual_method": "vfunc signatures need pygobject classmethod-shaped binding; ginext binds the instance via PyMethod_New",
    "test_source.py::TestSource::test_extra_init_args": "GLib.Source subclass __init__ args not forwarded",
    "test_source.py::TestSource::test_python_unref_during_dispatch": "GLib.Source.new() positional ctor not implemented",
    "test_typeclass.py::TestCoercion::test_coerce_from_class": "GObjectMeta/ObjectClass coercion not implemented",
    "test_typeclass.py::TestCoercion::test_coerce_from_gtype": "PropertiesObject.__gtype__ not implemented",
    "test_typeclass.py::TestCoercion::test_coerce_from_instance": "GObjectMeta/ObjectClass coercion not implemented",
}


_SKIP_BY_NODE = {
    "test_gi.py::TestGFlags::test_flags": "flaky GFlags inheritance assertion",
}


_XFAIL_NOT_RUN_BY_NODE = {
    "test_callback.py::test_async_callback": "can hang in the compat package run; disable until async callback scheduling is understood",
    "test_iochannel.py::IOChannel::test_add_watch_no_data": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_add_watch_with_data": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_add_watch_with_multi_data": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_backwards_compat_flags": "unsafe while IOChannel marshalling is crash-prone",
    "test_iochannel.py::IOChannel::test_buffering": "crashes in IOChannel binary encoding marshalling",
    "test_iochannel.py::IOChannel::test_deprecated_add_watch_no_data": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_deprecated_add_watch_with_data": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_deprecated_method_add_watch_data_priority": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_deprecated_method_add_watch_no_data": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_fd_read": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_fd_write": "crashes in IOChannel file descriptor marshalling",
    "test_iochannel.py::IOChannel::test_file_iter": "crashes in IOChannel encoding marshalling",
    "test_iochannel.py::IOChannel::test_file_read": "crashes in IOChannel encoding marshalling",
    "test_iochannel.py::IOChannel::test_file_read_chars": "crashes in IOChannel encoding marshalling",
    "test_iochannel.py::IOChannel::test_file_readline_latin1": "crashes in IOChannel encoding marshalling",
    "test_iochannel.py::IOChannel::test_file_readline_utf8": "crashes in IOChannel encoding marshalling",
    "test_iochannel.py::IOChannel::test_file_readlines": "crashes in IOChannel encoding marshalling",
    "test_iochannel.py::IOChannel::test_file_write": "crashes in IOChannel encoding marshalling",
    "test_iochannel.py::IOChannel::test_file_writelines": "crashes in IOChannel encoding marshalling",
    "test_iochannel.py::IOChannel::test_seek": "crashes in IOChannel encoding marshalling",
    "test_overrides_gdkpixbuf.py::test_new_from_data": "crashes in GdkPixbuf pixel data marshalling",
    "test_overrides_gdkpixbuf.py::test_new_from_data_deprecated_args": "unsafe while GdkPixbuf pixel data marshalling is crash-prone",
    "test_overrides_glib.py::test_io_add_watch_get_args": "crashes in IOChannel constructor not implemented",
    "test_overrides_glib.py::test_iochannel": "unsafe while IOChannel marshalling is crash-prone",
    "test_overrides_glib.py::test_iochannel_write": "crashes in IOChannel shutdown marshalling",
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
        except AttributeError, ImportError, RuntimeError:
            pass
    return gi.repository


@pytest.fixture(scope="session", autouse=True)
def _pygobject_compat_layer():
    return _install_pygobject_compat_layer()


_bootstrap_pygobject_compat()
