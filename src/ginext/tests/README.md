# ginext Test Suite Map

This directory contains focused ginext runtime tests, compatibility tests
ported from PyGObject, and backlog tests that document known gaps. Use this map
to choose the narrowest useful test command before running the full suite.

Run focused selections through the Makefile so the build directory, typelibs,
and Python path are set correctly:

```sh
PYTEST_ARGS='src/ginext/tests/<area>/test_name.py -q -n 0' make test
```

## Areas

| Area | What it covers | Test files |
| --- | --- | --- |
| `boxed/` | Boxed value wrapping, field arrays, ownership, and GResource boxed behavior. | `test_boxed.py`, `test_boxed_field_array.py`, `test_boxed_resource.py` |
| `cairo/` | Cairo foreign type interop backlog for Regress return and round-trip APIs. | `test_foreign_backlog.py` |
| `classbuild/` | Lazy GI class creation, class caching, parent inheritance, subclass compatibility, base lookup through namespaces, and managed instance dictionaries. | `test_base_via_namespace.py`, `test_class_caching.py`, `test_class_creation.py`, `test_managed_dict_store_attr.py`, `test_parent_inheritance.py`, `test_subclass_gtype_compat.py`, `test_subclass_with_gobject_class_attr.py` |
| `closure/` | Signal closure smoke tests, callback ownership/lifetime invariants, and `GClosure` argument conversion. | `test_gclosure_argument.py`, `test_ownership_invariants.py`, `test_smoke.py` |
| `constructor/` | Constructor keyword handling and rejection of abstract type construction. | `test_abstract_type_rejection.py`, `test_kwargs_construction.py` |
| `defaults/` | Namespace default-version resolution, environment overrides, suffixed imports, app-specific defaults, and discovery. | `test_app_selection.py`, `test_env_versions_override.py`, `test_gidefaults_discovery.py`, `test_highest_installed_fallback.py`, `test_implied_defaults.py`, `test_resolution_order.py`, `test_suffixed_imports.py` |
| `enum/` | Enum method support and Python-defined enum/flag backlog. | `test_enum_methods.py`, `test_python_defined_enum_flags.py` |
| `features/` | Runtime feature flags and feature gating behavior. | `test_feature_flags.py` |
| `gio/` | Focused Gio coverage: `Application`, async APIs, DBus backlog, `Cancellable`, `File`, `ListStore`, menu/action types, app info, input streams, volume monitors, and file interface compatibility. | `test_Gio_Async.py`, `test_Gio_DBus.py`, `test_app_info.py`, `test_application.py`, `test_cancellable.py`, `test_file.py`, `test_file_interface_compat.py`, `test_input_stream.py`, `test_list_store.py`, `test_menu.py`, `test_simple_action.py`, `test_volume_monitor.py` |
| `glib/` | GLib constants, scalar helpers, `Bytes`, `Error`, Unicode helpers, logging writer hooks, and `Variant` compatibility backlog. | `test_bytes.py`, `test_constants.py`, `test_core.py`, `test_error.py`, `test_log_set_writer_func.py`, `test_unichar.py`, `test_variant_compat.py` |
| `gobject/` | GObject type constants, registration, inheritance, object API, lifecycle, vfunc backlog, type functions, `connect_object` GC, and ParamSpec introspection backlog. | `test_GObject_Object.py`, `test_GObject_Object_vfunc.py`, `test_GObject_Type.py`, `test_connect_object_gc.py`, `test_gtype_constants.py`, `test_inheritance.py`, `test_object_api.py`, `test_object_lifecycle.py`, `test_paramspec_introspection_backlog.py`, `test_registration.py`, `test_type_functions.py` |
| `gst/` | GStreamer clock ID and buffer compatibility backlog. | `test_buffer_backlog.py`, `test_clockid_backlog.py` |
| `gtk3/` | GTK 3 compatibility: application, atoms, buttons, templates, text buffers/views, tree paths, CSS providers, list boxes, widget backlog, GDK event unions, and unsupported argument inventory. | `test_Gtk_Template.py`, `test_Gtk_TextBuffer.py`, `test_application.py`, `test_atoms.py`, `test_button.py`, `test_cssprovider_backlog.py`, `test_gdk_event_union_backlog.py`, `test_listbox_backlog.py`, `test_template.py`, `test_textview_backlog.py`, `test_tree_path.py`, `test_unsupported_argument_args.py`, `test_widget_compat_backlog.py` |
| `gtk4/` | GTK 4 compatibility: application, adjustment, box backlog, builder, button, entry completion, expression backlog, scale, templates, text buffers, and text iter. | `test_adjustment.py`, `test_application.py`, `test_box.py`, `test_builder.py`, `test_button.py`, `test_entry_completion.py`, `test_expression_backlog.py`, `test_scale.py`, `test_template.py`, `test_text_iter.py`, `test_textbuffer_backlog.py` |
| `integration/` | Cross-layer integration, cache behavior, first vertical slice, runtime smoke coverage, and web browser extension probes. | `test_caches_layer_wide.py`, `test_first_vertical_slice.py`, `test_runtime_smoke.py`, `test_web_browser_extensions.py` |
| `inventory/` | Namespace inventory checks and snapshot-based unsupported argument coverage. | `test_core_namespace_inventory.py`, `test_unsupported_argument_args.py` |
| `invoke/` | Invocation layer argument and return behavior: ints, floats, strings, filenames, nullable args, keywords, strv arrays, enum/flags, descriptor rejection, PyArg oracles, and return type shapes. | `test_argchecks_gimarshalling.py`, `test_descriptor_build_rejection.py`, `test_enum_flags.py`, `test_filename_string.py`, `test_float.py`, `test_gee_callback_triples.py`, `test_int.py`, `test_keyword_args.py`, `test_nullable_args.py`, `test_pyargs_oracle.py`, `test_return_type_shapes.py`, `test_strv_array.py`, `test_utf8_string.py` |
| `method/` | Static method lookup and invocation. | `test_static_method.py` |
| `namespace/` | Lazy namespace objects, first access, attribute gateway behavior, namespace caching, unknown members, public surface, and JIT namespace loading. | `test_attribute_gateway.py`, `test_first_access.py`, `test_lazy_namespace_jit.py`, `test_namespace_attrs.py`, `test_namespace_caching.py`, `test_public_surface.py`, `test_unknown_member.py` |
| `overlay/` | Overlay API registration and lookup behavior. | `test_overlay_api.py` |
| `plan_invariant/` | Invocation plan cache invariants, stats API, and checks that hot paths avoid GI metadata lookups. | `test_no_gi_on_hot_path.py`, `test_plan_caching.py`, `test_stats_api.py` |
| `property/` | Python-defined GObject properties: value types, ParamSpec defaults/bounds, metadata, flags, lifetime, instance IO, signals, errors, and decorator backlog. | `test_decorator_forms_backlog.py`, `test_errors.py`, `test_flags.py`, `test_instance_io.py`, `test_lifetime.py`, `test_metadata.py`, `test_pspec_bounds.py`, `test_pspec_defaults.py`, `test_signals.py`, `test_value_types.py` |
| `pygobject/` | PyGObject compatibility suite imported under `gi.repository`, including GLib/Gio/GObject/GI marshalling, properties, signals, overrides, callbacks, async, DBus, Cairo, import machinery, signatures, fields, source/main loop behavior, and other historical compatibility cases. | See the dedicated section below. |
| `signal/` | Python-defined signals, emit/connect behavior, notify, one-shot handlers, owner policies, bound method weakening, constructor kwargs, attribute-form signals, and argument adapters. | `test_GObject_Object_gsignals.py`, `test_GObject_Object_signal.py`, `test_arg_adapter.py`, `test_attribute_form.py`, `test_bound_method_weakening.py`, `test_constructor_kwargs.py`, `test_emit.py`, `test_notify.py`, `test_once.py`, `test_owner_policy.py`, `test_python_defined_signals.py`, `test_signal_connection.py` |
| `struct/` | Struct construction, fields, copying, equality, and method behavior. | `test_structs.py` |
| `typelib/` | Tests against external typelibs and GI test libraries, including GIMarshallingTests, Regress, Fundamental, Unix regressions, keyword args, object inout, and utility APIs. | `test_fundamental.py`, `test_gi_marshalling_tests.py`, `test_keyword_args.py`, `test_object_inout.py`, `test_regress.py`, `test_regress_unix.py`, `test_utility.py` |
| `union/` | Union construction, fields, discriminators, and method behavior. | `test_unions.py` |

## PyGObject Compatibility Files

The `pygobject/` directory mirrors broad PyGObject compatibility behavior and
has its own local compatibility policy in `pygobject/conftest.py`.

- Core GI and marshalling: `test_gi.py`, `test_everything.py`,
  `test_fundamental.py`, `test_gtype.py`, `test_typeclass.py`,
  `test_fields.py`, `test_repository.py`, `test_resulttuple.py`,
  `test_signature.py`, `test_unknown.py`
- GLib/GObject/Gio APIs: `test_glib.py`, `test_gobject.py`, `test_gio.py`,
  `test_error.py`, `test_events.py`, `test_mainloop.py`, `test_source.py`,
  `test_iochannel.py`, `test_ossig.py`, `test_subprocess.py`,
  `test_thread.py`
- Object, property, signal, and callback compatibility: `test_properties.py`,
  `test_signal.py`, `test_callback.py`, `test_async.py`,
  `test_object_lifecycle.py`, `test_object_marshaling.py`,
  `test_interface.py`
- Overrides and toolkit integration: `test_overrides_gdk.py`,
  `test_overrides_gdkpixbuf.py`, `test_overrides_gio.py`,
  `test_overrides_glib.py`, `test_overrides_gobject.py`,
  `test_overrides_gtk.py`, `test_overrides_pango.py`,
  `test_gtk_template.py`, `test_atoms.py`, `test_cairo.py`
- Import, internal, and C/API compatibility: `test_import_machinery.py`,
  `test_internal_api.py`, `test_pycapi.py`, `test_docstring.py`,
  `test_enum.py`, `test_gdbus.py`

## Shared Fixtures And Helpers

- `conftest.py` contains session fixtures for common namespaces
  (`GLib`, `Gio`, `GObject`, `GType`, `Property`), shared object factories
  (`cancellable`, `unique_type_name`, `make_subclass`, `make_property_class`),
  ParamSpec readers, call-mode parametrization, and suite-wide markers, skips,
  xfails, and compatibility behavior.
- `gi_test_utils.py` contains helpers for tests that need the GI test
  libraries.
- `wayland_fixture.py` provides the session-scoped `wayland` fixture and
  compositor startup used by GTK tests.
- Area-level `conftest.py` files, such as `gtk3/conftest.py`,
  `gtk4/conftest.py`, and `pygobject/conftest.py`, provide display
  requirements and compatibility policy local to those areas.
- File-local fixtures should stay small and domain-specific: namespace imports,
  temporary files/directories, DBus/settings environments, simple model rows,
  or parametrized cases used by one test module. Promote a fixture to
  `conftest.py` when the same setup appears in several files.

## Backlog And Compatibility Tests

Files named `*_backlog.py` and explicit `xfail`/`skip` markers are intentional
documentation of known gaps or environment-dependent coverage. Do not remove
them just because they are not green in the default environment; update the
marker and this map when the behavior becomes supported.
