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

from conftest_shared import (
    configure_subprocess_marker,
    maybe_run_test_in_subprocess,
    setup_gi_test_env,
)

# The introspection test typelibs must be on GI_TYPELIB_PATH before ginext is
# first imported (the repository's search path is fixed at import). The detection
# lives once in conftest_shared; this directory is its own pytest rootdir (it's
# under src/, not the package tests/ tree), so it runs the setup itself.
setup_gi_test_env(Path(__file__).resolve().parents[5])


_XFAIL_BY_NODE = {
    "test_cancellable.py::test_does_not_expose_new": "constructor exposure differs after static constructor support",
    "test_enum_flags.py::test_enum_return_can_be_passed_back_as_arg": "enum/flags wrapper identity mismatch in combined compat run",
    "test_gi.py::TestModule::test_dir": "missing pygobject compat attribute",
    "test_gi.py::TestModule::test_path": "missing pygobject compat attribute",
    "test_gi.py::TestModule::test_str": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestModule::test_type": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestOverrides::test_constant": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestOverrides::test_module_name": "behaviour mismatch under ginext pygobject compat",
    "test_gi.py::TestOverrides::test_object": "TypeError under ginext pygobject compat",
    "test_gi.py::TestOverrides::test_struct": "TypeError under ginext pygobject compat",
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
    "test_gobject.py::test_gobject_weak_ref": "missing pygobject compat attribute",
    "test_gtk_template.py::test_finalization_of_custom_child_objects": "missing pygobject compat attribute",
    "test_gtk_template.py::test_internal_child": "missing pygobject compat attribute",
    "test_gtk_template.py::test_multiple_init_template_calls": "missing pygobject compat attribute",
    "test_gtk_template.py::test_python_class_hierarchy": "missing pygobject compat attribute",
    "test_gtk_template.py::test_signal_handler_with_object_does_not_leak_memory": "missing pygobject compat attribute",
    "test_gtk_template.py::test_template_hierarchy": "missing pygobject compat attribute",
    "test_import_machinery.py::TestImporter::test_invalid_repository_module_name": "behaviour mismatch under ginext pygobject compat",
    "test_import_machinery.py::TestImporter::test_require_version_warning": "TypeError under ginext pygobject compat",
    "test_import_machinery.py::TestModule::test_static_binding_protection": "module not exposed by ginext compat",
    "test_import_machinery.py::TestOverrides::test_load_overrides": "behaviour mismatch under ginext pygobject compat",
    "test_import_machinery.py::TestOverrides::test_non_gi": "behaviour mismatch under ginext pygobject compat",
    "test_import_machinery.py::TestOverrides::test_separate_path": "missing pygobject compat attribute",
    "test_internal_api.py::TestErrors::test_gerror": "missing pygobject compat attribute",
    "test_internal_api.py::TestErrors::test_no_gerror": "missing pygobject compat attribute",
    "test_internal_api.py::TestGValueConversion::test_int": "missing pygobject compat attribute",
    "test_internal_api.py::TestGValueConversion::test_int_array": "missing pygobject compat attribute",
    "test_internal_api.py::TestGValueConversion::test_str": "missing pygobject compat attribute",
    "test_internal_api.py::TestGValueConversion::test_str_array": "missing pygobject compat attribute",
    "test_internal_api.py::TestObject::test_create_ctor": "missing pygobject compat attribute",
    "test_internal_api.py::TestObject::test_new_refcount": "missing pygobject compat attribute",
    "test_internal_api.py::TestObject::test_pyobject_new_test_type": "missing pygobject compat attribute",
    "test_internal_api.py::test_constant_strip_prefix": "missing pygobject compat attribute",
    "test_internal_api.py::test_parse_constructor_args": "missing pygobject compat attribute",
    "test_internal_api.py::test_state_ensure_release": "missing pygobject compat attribute",
    "test_internal_api.py::test_to_unichar_conv": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_class_with_slots_raises_warning": "test relies on missing compat path",
    "test_object_lifecycle.py::test_object_constructed_after_init": "behaviour mismatch under ginext pygobject compat",
    "test_object_lifecycle.py::test_object_constructed_after_init_by_new": "behaviour mismatch under ginext pygobject compat",
    "test_object_lifecycle.py::test_object_with_instance_data_retains_data[DerivedObj]": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_object_with_instance_data_retains_data[TestObj]": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_object_with_post_init": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_object_with_post_init_and_interface": "behaviour mismatch under ginext pygobject compat",
    "test_object_lifecycle.py::test_object_with_post_init_created_by_new": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_object_with_post_init_raises_exception": "expected warning/exception not raised",
    "test_object_lifecycle.py::test_object_without_instance_data_gets_deleted[DerivedObj]": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_objects_with_cyclic_dependency_and_instance_dict": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_slot_object_can_be_created": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_slot_object_without_values_can_be_created": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_subclass_with_slots_raises_warning": "test relies on missing compat path",
    "test_object_lifecycle.py::test_value_object_retains_init_value": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_value_object_retains_object_property_value": "missing pygobject compat attribute",
    "test_object_lifecycle.py::test_value_object_retains_property_value": "missing pygobject compat attribute",
    "test_object_marshaling.py::TestVFuncsWithHeldFloatingArg::test_vfunc_in_floating_transfer_full_with_held_floating": "behaviour mismatch under ginext pygobject compat",
    "test_object_marshaling.py::TestVFuncsWithHeldFloatingArg::test_vfunc_in_floating_transfer_none_with_held_floating": "behaviour mismatch under ginext pygobject compat",
    "test_ossig.py::TestOverridesWakeupOnAlarm::test_gio_application": "TypeError under ginext pygobject compat",
    "test_overrides_gdk.py::TestGdk::test_file_list": "TypeError under ginext pygobject compat",
    "test_overrides_gdk.py::TestGdk::test_paintable_flags": "missing pygobject compat attribute",
    "test_overrides_gdk.py::TestGdk::test_rgba": "missing pygobject compat attribute",
    "test_overrides_gdk.py::TestGdk::test_rgba_representations": "TypeError under ginext pygobject compat",
    "test_overrides_gio.py::test_list_store_delitem_slice": "missing pygobject compat attribute",
    "test_overrides_gio.py::test_list_store_find_with_equal_func": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_gio.py::test_list_store_insert_sorted": "TypeError under ginext pygobject compat",
    "test_overrides_gio.py::test_list_store_setitem_slice": "missing pygobject compat attribute",
    "test_overrides_gio.py::test_list_store_sort": "marshalling not implemented",
    "test_overrides_gio.py::test_types_init_warn": "test relies on missing compat path",
    "test_overrides_gtk.py::TestBuilder::test_add_from_string": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestBuilder::test_builder": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestBuilder::test_builder_with_handler_and_args": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestBuilder::test_builder_with_handler_object": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestGtk::test_adjustment": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_gtk.py::TestGtk::test_dialog_add_buttons": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestGtk::test_dialog_classes": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestGtk::test_editable": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestGtk::test_iconview": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestGtk::test_inheritance": "Gtk3-only Action override leaks into gi.overrides.Gtk.__all__ under Gtk 4",
    "test_overrides_gtk.py::TestGtk::test_widget_drag_methods_gtk4": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestGtk::test_widget_iterable": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestGtk::test_window_gtk4": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_gtk.py::TestListStore::test_insert_with_values": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTextBuffer::test_backward_find_char": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTextBuffer::test_text_buffer": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestTextBuffer::test_text_buffer_search": "TypeError under ginext pygobject compat",
    "test_overrides_gtk.py::TestTextBuffer::test_text_iter": "missing pygobject compat attribute",
    "test_overrides_gtk.py::TestTreeModel::test_filter_new_default": "TypeError under ginext pygobject compat",
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
    "test_overrides_gtk.py::TestTreeModel::test_tree_store_insert_after_none": "TypeError under ginext pygobject compat",
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
    "test_overrides_gtk.py::test_css_provider_load_from_data[* { background: white; }0]": "Gtk.CssProvider.new pygobject ctor alias not implemented",
    "test_overrides_gtk.py::test_css_provider_load_from_data[* { background: white; }1]": "Gtk.CssProvider.new pygobject ctor alias not implemented",
    "test_overrides_gtk.py::test_wrapper_toggle_refs": "missing pygobject compat attribute",
    "test_overrides_pango.py::TestPango::test_font_description": "TypeError under ginext pygobject compat",
    "test_overrides_pango.py::TestPango::test_layout": "behaviour mismatch under ginext pygobject compat",
    "test_overrides_pango.py::TestPango::test_layout_set_markup": "TypeError under ginext pygobject compat",
    "test_overrides_pango.py::TestPango::test_layout_set_test": "TypeError under ginext pygobject compat",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_glist": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_glist_ctor": "boxed-glist Property from list ctor not implemented",
    "test_properties.py::TestCGetPropertyMethod::test_boxed_struct": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_char": "get_property() arity mismatch",
    "test_properties.py::TestCGetPropertyMethod::test_enum_values": "find_property() on class not implemented",
    "test_properties.py::TestCGetPropertyMethod::test_flags_values": "find_property() on class not implemented",
    "test_properties.py::TestCGetPropertyMethod::test_setting_several_properties": "set_properties() not implemented",
    "test_properties.py::TestCGetPropertyMethod::test_uchar": "get_property() arity mismatch",
    "test_properties.py::TestCPropsAccessor::test_boxed_glist": "boxed-glist Property accessor not implemented",
    "test_properties.py::TestCPropsAccessor::test_boxed_glist_ctor": "boxed-glist Property from list ctor not implemented",
    "test_properties.py::TestCPropsAccessor::test_boxed_struct": "boxed-struct Property accessor not implemented",
    "test_properties.py::TestCPropsAccessor::test_char": "Property overflow validation not implemented",
    "test_properties.py::TestCPropsAccessor::test_enum_values": "find_property() on class not implemented",
    "test_properties.py::TestCPropsAccessor::test_flags_values": "find_property() on class not implemented",
    "test_properties.py::TestCPropsAccessor::test_param_spec_dir": "Property dir() lookup not implemented",
    "test_properties.py::TestCPropsAccessor::test_props_accessor_dir": "props accessor dir() not implemented",
    "test_properties.py::TestCPropsAccessor::test_setting_several_properties": "set_properties() not implemented",
    "test_properties.py::TestCPropsAccessor::test_uchar": "Property overflow validation not implemented",
    "test_properties.py::TestProperty::test_custom_setter": "Property descriptor name lookup not implemented",
    "test_properties.py::TestProperty::test_decorator_default": "Property type=python-type not implemented",
    "test_properties.py::TestProperty::test_decorator_private_setter": "Property type=python-type not implemented",
    "test_properties.py::TestProperty::test_decorator_with_call": "Property setter() chain not implemented",
    "test_properties.py::TestProperty::test_doc_strings": "Property type=python-type not implemented",
    "test_properties.py::TestProperty::test_errors": "Property TypeError validation not implemented",
    "test_properties.py::TestProperty::test_generic_instance_property": "subscriptable generic type for Property not implemented",
    "test_properties.py::TestProperty::test_getter_exception": "get_property() arity mismatch",
    "test_properties.py::TestProperty::test_min_max": "Property min/max enforcement not implemented",
    "test_properties.py::TestProperty::test_object_property": "obj-typed Property not implemented",
    "test_properties.py::TestProperty::test_property_subclass_custom_setter_error": "Property setter error propagation not implemented",
    "test_properties.py::TestProperty::test_python_to_glib_type_mapping": "Property._type_from_python helper not implemented",
    "test_properties.py::TestProperty::test_range": "Property descriptor name lookup not implemented",
    "test_properties.py::TestProperty::test_simple": "Property default not surfaced",
    "test_properties.py::TestPropertyInheritanceObject::test_override_gi_property": "missing pygobject compat attribute",
    "test_properties.py::TestPropertyObject::test_boxed": "marshalling not implemented",
    "test_properties.py::TestPropertyObject::test_construct_only": "behaviour mismatch under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_enum": "marshalling not implemented",
    "test_properties.py::TestPropertyObject::test_flags": "behaviour mismatch under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_hasattr_on_class": "behaviour mismatch under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_int_to_str": "TypeError under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_interface": "no GValue conversion for GFile interface property",
    "test_properties.py::TestPropertyObject::test_iteration": "TypeError under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_iterator_protocol_for_properties": "TypeError under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_multi": "set_properties() not implemented",
    "test_properties.py::TestPropertyObject::test_range": "Property.{int,...} descriptor accessors not implemented",
    "test_properties.py::TestPropertyObject::test_repr": "behaviour mismatch under ginext pygobject compat",
    "test_properties.py::TestPropertyObject::test_set_on_class": "Property descriptor class-set not implemented",
    "test_properties.py::TestPropertyObject::test_utf8_lone_surrogate": "string handling differs under ginext",
    "test_properties.py::test_get_function_property": "function-typed Property not implemented",
    "test_properties.py::test_gobject_inheritance_with_incomplete_initialization": "gimeta not surfaced on incomplete GObject subclass",
    "test_repository.py::Test::test_arg_info": "Repository.require not implemented",
    "test_repository.py::Test::test_async_method_finish_func": "Repository.require not implemented",
    "test_repository.py::Test::test_base_info": "Repository.require not implemented",
    "test_repository.py::Test::test_callable_can_throw_gerror": "Repository.require not implemented",
    "test_repository.py::Test::test_callable_info": "Repository.require not implemented",
    "test_repository.py::Test::test_callable_inheritance": "Repository.require not implemented",
    "test_repository.py::Test::test_enum_info": "Repository.require not implemented",
    "test_repository.py::Test::test_enums": "Repository.require not implemented",
    "test_repository.py::Test::test_field_info": "Repository.require not implemented",
    "test_repository.py::Test::test_fundamental_object_info": "Repository.require not implemented",
    "test_repository.py::Test::test_interface_info": "Repository.require not implemented",
    "test_repository.py::Test::test_introspected_argument_info": "Repository.require not implemented",
    "test_repository.py::Test::test_method_finish_func": "Repository.require not implemented",
    "test_repository.py::Test::test_method_info": "Repository.require not implemented",
    "test_repository.py::Test::test_notify_signal_info_with_obj": "Repository.require not implemented",
    "test_repository.py::Test::test_object_constructor": "Repository.require not implemented",
    "test_repository.py::Test::test_object_info": "Repository.require not implemented",
    "test_repository.py::Test::test_property_info": "Repository.require not implemented",
    "test_repository.py::Test::test_registered_type_info": "Repository.require not implemented",
    "test_repository.py::Test::test_repo_get_dependencies": "Repository.require not implemented",
    "test_repository.py::Test::test_repo_get_immediate_dependencies": "Repository.require not implemented",
    "test_repository.py::Test::test_repo_is_registered": "Repository.require not implemented",
    "test_repository.py::Test::test_signal_info": "Repository.require not implemented",
    "test_repository.py::Test::test_struct_info": "Repository.require not implemented",
    "test_repository.py::Test::test_type_info": "Repository.require not implemented",
    "test_repository.py::Test::test_union_info": "Repository.require not implemented",
    "test_repository.py::Test::test_vfunc_info": "Repository.require not implemented",
    "test_signal.py::TestIntrospectedSignals::test_intarray_ret": "signal return GValue conversion is not ABI-profile aware",
    "test_signature.py::Test::test_allow_none_with_user_data_defaults": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_array": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_boolean": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_boxed": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_conflict": "inspect.signature() on GI vfuncs not implemented",
    "test_signature.py::Test::test_arg_double": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_enum": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_filename": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_flags": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_float": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_garray": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_genum": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_gflags": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_ghashtable": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_glist": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_gslist": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_gtype": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_gvalue": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_int16": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_int32": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_int64": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_int8": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_ptrarray": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_struct": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_uint16": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_uint32": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_uint64": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_uint8": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_arg_utf8": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_in_arg": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_init_function": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_inout_arg": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_object_constructor": "GObject.new pygobject ctor alias not implemented",
    "test_signature.py::Test::test_object_full_inout": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_object_method": "inspect.signature() on GI methods not implemented",
    "test_signature.py::Test::test_object_static_method": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_object_virtual_method": "inspect.signature() on GI vfuncs not implemented",
    "test_signature.py::Test::test_out_arg": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_return": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_return_multiple": "inspect.signature() on GI callables not implemented",
    "test_signature.py::Test::test_signature_attr": "callable __signature__ attribute not implemented",
    "test_source.py::TestSource::test_extra_init_args": "GLib.Source subclass __init__ args not forwarded",
    "test_source.py::TestSource::test_python_unref_during_dispatch": "GLib.Source.new() positional ctor not implemented",
    "test_typeclass.py::TestCoercion::test_coerce_from_class": "GObjectMeta/ObjectClass coercion not implemented",
    "test_typeclass.py::TestCoercion::test_coerce_from_gtype": "PropertiesObject.__gtype__ not implemented",
    "test_typeclass.py::TestCoercion::test_coerce_from_instance": "GObjectMeta/ObjectClass coercion not implemented",
}

_COMBINED_XFAIL_BY_NODE = {
    "test_everything.py::TestBoxed::test_boxed": "boxed property wrapper type mismatch in combined compat run",
}


def pytest_configure(config: pytest.Config) -> None:
    configure_subprocess_marker(config)


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    return maybe_run_test_in_subprocess(pyfuncitem)


_XFAIL_NOT_RUN_BY_NODE = {
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
    "test_overrides_gio.py::test_list_store_setitem_simple": "crashes in Gio.ListStore splice marshalling",
    "test_overrides_glib.py::test_io_add_watch_get_args": "crashes in IOChannel constructor not implemented",
    "test_overrides_glib.py::test_iochannel": "unsafe while IOChannel marshalling is crash-prone",
    "test_overrides_glib.py::test_iochannel_write": "crashes in IOChannel shutdown marshalling",
    "test_properties.py::TestCPropsAccessor::test_parent_class": "crashes setting parent class property via compat props proxy",
}


_XFAIL_NOT_RUN_DEBUG_BY_NODE = {
    "test_overrides_gtk.py::TestTreeModel::test_tree_store": "crashes xdist worker in debug Python builds",
    "test_properties.py::TestCPropsAccessor::test_unichar": "triggers ASAN/UBSAN crash in ParamSpec numeric info for unichar properties",
}


_FREE_THREADED_XFAIL_BY_NODE = {
    "test_gtk_template.py::test_init_template_second_instance": "Gtk template child binding is unstable under free-threaded Python",
    "test_gtk_template.py::test_internal_child": "Gtk template child binding is unstable under free-threaded Python",
    "test_gtk_template.py::test_main_example": "Gtk template child binding is unstable under free-threaded Python",
}

_FREE_THREADED_XFAIL_NOT_RUN_BY_NODE = {
    "test_signal.py::TestGSignalsError::test_invalid_type": "crashes xdist worker under free-threaded Python",
}

_PY315_GIL_XFAIL_NOT_RUN_BY_NODE = {
    "test_properties.py::TestCPropsAccessor::test_held_object_ref_count_getter": "crashes xdist worker on Python 3.15 GIL build during refcount GC",
}


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item: pytest.Item) -> object:
    # ginext native tests call features.reset_for_test() in teardown, which
    # reverts pygobject_compat to its default (off). Under importlib mode pytest
    # imports the gi/tests package __init__ lazily during this setup phase, and
    # that import pulls in `gi`, which raises unless compat is on. Re-assert it
    # here (before the package import runs) so a prior native test on the same
    # xdist worker can't leave the flag off. Scoped to gi tests via this
    # conftest's directory.
    import ginext

    ginext.features.set_enabled("pygobject_compat", True)
    return (yield)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    is_debug_python = hasattr(sys, "gettotalrefcount")
    is_py315_gil = sys.version_info >= (3, 15) and getattr(
        sys, "_is_gil_enabled", lambda: True
    )()
    is_free_threaded = not getattr(sys, "_is_gil_enabled", lambda: True)()
    is_xdist_worker = bool(os.environ.get("PYTEST_XDIST_WORKER"))
    is_large_combined_run = len(items) > 100
    for item in items:
        _, sep, relative_nodeid = item.nodeid.rpartition("/gi/tests/")
        if not sep:
            continue
        if (
            is_free_threaded
            and not is_xdist_worker
            and relative_nodeid in _FREE_THREADED_XFAIL_BY_NODE
        ):
            reason = _FREE_THREADED_XFAIL_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, strict=False))
            continue
        if is_free_threaded and relative_nodeid in _FREE_THREADED_XFAIL_NOT_RUN_BY_NODE:
            reason = _FREE_THREADED_XFAIL_NOT_RUN_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, run=False, strict=False))
            continue
        if is_py315_gil and relative_nodeid in _PY315_GIL_XFAIL_NOT_RUN_BY_NODE:
            reason = _PY315_GIL_XFAIL_NOT_RUN_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, run=False, strict=False))
            continue
        if is_large_combined_run and relative_nodeid in _COMBINED_XFAIL_BY_NODE:
            reason = _COMBINED_XFAIL_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, strict=False))
            continue
        if relative_nodeid.startswith("test_cairo.py::TestPango::") and (
            not has_display or is_debug_python or is_free_threaded
        ):
            item.add_marker(
                pytest.mark.skip(
                    reason="Gtk cairo font-options test is not stable under debug/display-limited/free-threaded runs",
                )
            )
            continue
        if is_debug_python and relative_nodeid in _XFAIL_NOT_RUN_DEBUG_BY_NODE:
            reason = _XFAIL_NOT_RUN_DEBUG_BY_NODE[relative_nodeid]
            item.add_marker(pytest.mark.xfail(reason=reason, run=False, strict=False))
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
    # GI_TYPELIB_PATH / LD_LIBRARY_PATH for the test typelibs are set once at
    # module import (via conftest_shared.setup_gi_test_env) before ginext loads.
    _compile_test_gsettings_schemas()
    os.environ.setdefault("GSETTINGS_BACKEND", "memory")
    return _install_pygobject_compat_layer()


def pytest_configure(config: pytest.Config) -> None:
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


@pytest.fixture(scope="session")
def wayland():
    return {}


_bootstrap_pygobject_compat()
