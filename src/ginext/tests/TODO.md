# ginext Test Backlog

This file tracks test modules that are not fully green in the default ginext
test environment. It is a backlog index, not a replacement for the executable
marks in the tests. Keep it in sync when adding, removing, or changing `xfail`,
`skip`, or known-failure coverage.

Last refreshed: 2026-05-22 with `cpython-3.14t`.

## Current Summary

| Phase | Passed | Failed | Errors | Skipped | Xfailed | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Non-GTK3 suite | 2708 | 0 | 0 | 136 | 874 | Default `-m "not gtk3"` phase. |
| GTK3 suite | 14 | 0 | 0 | 6 | 82 | `GINEXT_VERSIONS=Gtk:3.0`, `-m gtk3`. |
| Combined | 2722 | 0 | 0 | 142 | 956 | Collection-level skips that run in both phases are counted twice. |

`F`, `E`, `S`, and `X` below mean failed, error, skipped, and expected-failed
test counts for that module in the refreshed reports. There are currently no
real failing or erroring tests in the default Makefile-shaped environment.

## By Directory

### `boxed/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_boxed_field_array.py` | `S=0 X=4` | `boxed`, `field-array`, `DBus` | DBus node/interface/argument field-array wrappers; ported goi coverage is still marked not-run until the APIs are adapted to ginext. |
| `test_boxed_resource.py` | `S=0 X=8` | `boxed`, `GResource`, `Gdk.RGBA` | GResource boxed wrapping, registration, lookup, and GDK boxed constructor aliases; ported goi cases remain pending. |

### `cairo/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_foreign_backlog.py` | `S=2 X=0` | `cairo`, `foreign-types`, `optional-dep` | Cairo foreign type interop for Regress APIs; skipped in both pytest phases because `pycairo` is not installed in the default environment. |

### `classbuild/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_managed_dict_store_attr.py` | `S=0 X=1` | `classbuild`, `managed-dict`, `rewrap` | Python subclass instance dictionaries across wrapper re-creation; qdata/dict restoration across rewrap is pending. |

### `constructor/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_abstract_type_rejection.py` | `S=1 X=0` | `constructor`, `abstract-types`, `environment` | Abstract class construction rejection; skipped because no abstract class is available to probe in this environment. |

### `defaults/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_highest_installed_fallback.py` | `S=1 X=0` | `defaults`, `typelib-version`, `environment` | Highest installed typelib fallback; one case needs multiple installed GLib typelibs and is skipped when only one is present. |

### `enum/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_enum_methods.py` | `S=0 X=1` | `enum`, `classmethod`, `goi-port` | Enum method binding, specifically `Gst.Message.parse_type` classmethod shape; goi port still pending. |
| `test_python_defined_enum_flags.py` | `S=0 X=7` | `enum`, `flags`, `python-defined-types` | Python-defined `GObject.GEnum` and `GObject.GFlags` registration, values, type names, and string conversion. |

### `gio/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_Gio_Async.py` | `S=0 X=9` | `Gio`, `async`, `callbacks` | Async callback arity, named parameters, `GAsyncReadyCallback`, and user-data dropping; goi port remains pending. |
| `test_Gio_DBus.py` | `S=0 X=4` | `Gio`, `DBus`, `callbacks` | DBus callback and registration compatibility; goi port remains pending. |
| `test_application.py` | `S=0 X=8` | `Gio.Application`, `vfuncs`, `mainloop` | Gio.Application vfunc dispatch and lifecycle coverage; DBus register vfunc currently segfaults and needs a safe harness before direct assertions are reliable. |

### `glib/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_error.py` | `S=0 X=7` | `GLib.Error`, `GBoxed`, `exceptions` | GLib.Error exception inheritance, construction, matching, and quark/string domains; blocked by GBoxed layout versus Python exception layout. |

### `gobject/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_GObject_Object.py` | `S=0 X=8` | `GObject.Object`, `compat`, `goi-port` | Ported object API behavior still awaiting adaptation to ginext. |
| `test_GObject_Object_vfunc.py` | `S=0 X=11` | `GObject.Object`, `vfuncs`, `goi-port` | Object vfunc override and chain-up behavior from goi compatibility coverage. |
| `test_GObject_Type.py` | `S=0 X=12` | `GType`, `type-system`, `goi-port` | GObject type API coverage from goi compatibility tests. |
| `test_object_lifecycle.py` | `S=0 X=11` | `GObject.Object`, `lifecycle`, `goi-port` | Object lifecycle behavior from goi tests, including wrapper and disposal paths still pending. |
| `test_paramspec_introspection_backlog.py` | `S=0 X=49` | `ParamSpec`, `introspection`, `list-properties` | Introspected `GObjectClass.list_properties` ParamSpec wrapper behavior. |

### `gst/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_buffer_backlog.py` | `S=0 X=4` | `GStreamer`, `buffer`, `coverage` | GStreamer buffer compatibility backlog. |
| `test_clockid_backlog.py` | `S=0 X=4` | `GStreamer`, `clock-id`, `coverage` | GStreamer clock ID compatibility backlog. |

### `gtk3/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_Gtk_Template.py` | `S=0 X=15` | `GTK3`, `templates`, `goi-port` | Gtk.Template decorators, children, callbacks, and class metadata from goi compatibility coverage. |
| `test_Gtk_TextBuffer.py` | `S=0 X=2` | `GTK3`, `TextBuffer`, `goi-port` | Gtk.TextBuffer iterator return shapes from goi compatibility coverage. |
| `test_atoms.py` | `S=0 X=0` | `GTK3`, `Gdk.Atom`, `arrays` | Gdk.Atom array marshalling compatibility now passes. |
| `test_cssprovider_backlog.py` | `S=0 X=4` | `GTK3`, `CssProvider`, `overlays` | `Gtk.CssProvider.load_from_data` string, bytes, bytearray, and length compatibility. |
| `test_gdk_event_union_backlog.py` | `S=0 X=7` | `GTK3`, `Gdk.Event`, `unions` | Tagged boxed-union overlay behavior for Gdk.Event arms and parent lifetime. |
| `test_listbox_backlog.py` | `S=0 X=3` | `GTK3`, `ListBox`, `callbacks` | `Gtk.ListBox.bind_model` factory arity, user-data, and returned-widget lifetime. |
| `test_template.py` | `S=0 X=4` | `GTK3`, `templates`, `native-support` | Native ginext Gtk.Template API exposure, child binding, callbacks, and constructor validation. |
| `test_textview_backlog.py` | `S=0 X=32` | `GTK3`, `TextView`, `TextBuffer` | TextBuffer/TextView overlays: tags, marks, default lengths, insertion helpers, selection bounds, search, and iterator relocation. |
| `test_unsupported_argument_args.py` | `S=1 X=0` | `GTK3`, `inventory`, `snapshot` | Unsupported argument snapshot coverage; skipped because the snapshot has no Gtk-3.0-family entries. |
| `test_widget_compat_backlog.py` | `S=0 X=15` | `GTK3`, `Widget`, `compat` | Focused widget compatibility: enums, visibility/name, size requests, windows, boxes, labels, and application basics. |

### `gtk4/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_template.py` | `S=0 X=4` | `GTK4`, `templates`, `native-support` | Native ginext Gtk.Template support for GTK4. |
| `test_textbuffer_backlog.py` | `S=0 X=32` | `GTK4`, `TextBuffer`, `TextIter` | GTK4 TextBuffer/TextIter overlays mirroring PyGObject convenience behavior. |

### `integration/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_caches_layer_wide.py` | `S=1 X=0` | `integration`, `caches`, `PyGObject` | Cross-layer cache behavior when importing `gi.repository`; skipped because system PyGObject is unavailable. |

### `inventory/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_unsupported_argument_args.py` | `S=0 X=7` | `inventory`, `unsupported-args`, `callbacks` | Snapshot-based unsupported argument coverage for unresolved Vala class-nested callbacks that appear in GIR XML but not compiled typelibs. |

### `invoke/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_pyargs_oracle.py` | `S=14 X=0` | `invoke`, `CPython`, `debug-build` | PyArg parsing oracle checks; skipped under normal CPython and exercised by `make test-debug`. |

### `plan_invariant/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_no_gi_on_hot_path.py` | `S=0 X=1` | `plan-cache`, `stats`, `hot-path` | Hot-path checks for avoiding GI metadata calls; plan/build stats split is not exposed in the current ginext slice. |

### `property/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_decorator_forms_backlog.py` | `S=0 X=21` | `GObject.Property`, `decorators`, `compat` | PyGObject decorator forms for properties, setters, getters, defaults, docs, and validation. |

### `pygobject/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_async.py` | `S=0 X=8` | `PyGObject`, `async`, `GLib` | GLib asyncio event loop compatibility and async helper behavior. |
| `test_atoms.py` | `S=7 X=0` | `PyGObject`, `Gdk.Atom`, `GTK-version` | Gdk.Atom compatibility; skipped under GTK4 because Gdk4 does not have GdkAtom. |
| `test_cairo.py` | `S=32 X=0` | `PyGObject`, `cairo`, `optional-dep` | Cairo, Pango Cairo, region, and signal marshaling coverage; skipped without cairo support. |
| `test_callback.py` | `S=0 X=2` | `PyGObject`, `callbacks`, `async` | Regress async callback extra-argument compatibility. |
| `test_docstring.py` | `S=0 X=15` | `PyGObject`, `docstrings`, `introspection` | Callable docstring compatibility for GI functions and methods. |
| `test_enum.py` | `S=0 X=5` | `PyGObject`, `enum`, `flags` | PyGObject GEnum/GFlags declaration compatibility. |
| `test_error.py` | `S=0 X=14` | `PyGObject`, `GLib.Error`, `exceptions` | GLib.Error type, marshalling, and exception behavior. |
| `test_events.py` | `S=8 X=2` | `PyGObject`, `asyncio`, `mainloop` | GLib event loop policy, `asyncio.run`, subprocess watcher, and signal integration; includes a not-run free-threaded teardown segfault marker. |
| `test_everything.py` | `S=0 X=24` | `PyGObject`, `Regress`, `marshalling` | Broad Regress marshalling: arrays, callbacks, boxed values, closures, GValue, errors, and the remaining skip-return-value shapes. |
| `test_fields.py` | `S=0 X=9` | `PyGObject`, `fields`, `records` | Record field compatibility for arrays, objects, lists, pointers, and ownership. |
| `test_fundamental.py` | `S=0 X=20` | `PyGObject`, `fundamental`, `GValue` | Fundamental type constructors, `__gtype__`, pointer returns, and GObject.Value compatibility. |
| `test_gdbus.py` | `S=0 X=10` | `PyGObject`, `GDBus`, `Variant` | GDBus proxy registration and remaining GLib.Variant compatibility. |
| `test_gi.py` | `S=2 X=48` | `PyGObject`, `GI`, `marshalling` | Core GI compatibility: arrays, GValue, interfaces, modules, overrides, keyword args, transfer/refcount behavior, and error-message parity; enum/flags in/out/return identity, structures, deprecation helpers, keyword aliases, project version metadata, ParamSpec returns, object constructors, object `repr`, vfunc exception return handling, GHashTable int input validation, and object-property reads now pass; one non-Unicode path case is skipped by GLib, and `TestGFlags::test_flags` is skipped while its flaky GFlags inheritance assertion is investigated. |
| `test_gio.py` | `S=0 X=2` | `PyGObject`, `Gio`, `compat-attrs` | Gio, GApplication, GSettings, and most platform helpers now pass; remaining coverage is limited to one deprecated Unix function path and the Unix-specific DesktopAppInfo behavior mismatch. |
| `test_glib.py` | `S=0 X=31` | `PyGObject`, `GLib`, `platform` | GLib and platform compatibility, including missing attributes, TypeError parity, and behavior mismatches. |
| `test_gobject.py` | `S=0 X=42` | `PyGObject`, `GObject`, `GValue` | GObject API, GValue, property bindings, reference counting, and context-manager compatibility. |
| `test_gtk_template.py` | `S=2 X=5` | `PyGObject`, `Gtk.Template`, `GTK4` | Gtk.Template compatibility; two cases skip because GTK4 errors before the expected compatibility assertion, while init-template, handler, constructor, resource/file, and property-override coverage now pass. |
| `test_gtype.py` | `S=0 X=15` | `PyGObject`, `GType`, `type-functions` | GType module-level and type-function compatibility. |
| `test_import_machinery.py` | `S=0 X=8` | `PyGObject`, `imports`, `overrides` | Importer, module, and override loading behavior. |
| `test_interface.py` | `S=0 X=2` | `PyGObject`, `interfaces`, `unknown-wrapper` | Interface implementation and unknown interface wrapper compatibility. |
| `test_internal_api.py` | `S=0 X=13` | `PyGObject`, `private-api`, `GValue` | Private/internal API, errors, GValue conversion, and object helpers. |
| `test_iochannel.py` | `S=0 X=20` | `PyGObject`, `IOChannel`, `TypeError` | GLib.IOChannel constructor and method compatibility. |
| `test_mainloop.py` | `S=0 X=1` | `PyGObject`, `MainLoop`, `signals` | SIGINT handling under ginext PyGObject compatibility. |
| `test_object_lifecycle.py` | `S=0 X=20` | `PyGObject`, `lifecycle`, `compat-paths` | Object wrapper lifecycle, warning behavior, and missing compatibility paths. |
| `test_object_marshaling.py` | `S=0 X=8` | `PyGObject`, `object-marshalling`, `vfuncs` | Vfunc object argument transfer, floating refs, and crash-marked compatibility cases. |
| `test_ossig.py` | `S=2 X=3` | `PyGObject`, `signals`, `GTK-version` | OS signal override behavior; GTK3-only cases skip under GTK4. |
| `test_overrides_gdk.py` | `S=18 X=4` | `PyGObject`, `Gdk`, `overrides` | GDK override compatibility; many cases skip because they are not in Gdk4. |
| `test_overrides_gdkpixbuf.py` | `S=0 X=2` | `PyGObject`, `GdkPixbuf`, `overrides` | GdkPixbuf override attributes and expected warning/exception parity. |
| `test_overrides_gio.py` | `S=0 X=11` | `PyGObject`, `Gio`, `overrides` | Gio override compatibility: missing attributes, TypeError parity, marshalling, and missing compat paths; list-model sequence helpers now pass. |
| `test_overrides_glib.py` | `S=2 X=9` | `PyGObject`, `GLib`, `overrides` | GLib overrides; GVariant constructor/container/protocol coverage now passes, with remaining GVariant xfails limited to GLib.Error parse-error behavior; Windows-only tests skip on Linux. |
| `test_overrides_gobject.py` | `S=0 X=21` | `PyGObject`, `GObject`, `overrides` | GObject override compatibility: missing attributes, TypeError parity, and behavior mismatches. |
| `test_overrides_gtk.py` | `S=38 X=59` | `PyGObject`, `Gtk`, `overrides` | GTK override compatibility across Builder, container/tree APIs, signals, TextBuffer, widgets, and GTK3-only APIs under GTK4; builder handler extraction and one file-chooser dialog case now pass. |
| `test_overrides_pango.py` | `S=0 X=4` | `PyGObject`, `Pango`, `overrides` | Pango override TypeError and behavior parity. |
| `test_properties.py` | `S=0 X=77` | `PyGObject`, `properties`, `GValue` | Property descriptors, C property accessors, get/set arity, Python type properties, overflow validation, list/hash-table accessors, and object property marshalling. |
| `test_pycapi.py` | `S=0 X=1` | `PyGObject`, `C-API`, `capsule` | PyGObject private C API capsule exposure. |
| `test_repository.py` | `S=0 X=27` | `PyGObject`, `Repository`, `require` | `GIRepository.Repository.require` compatibility. |
| `test_signal.py` | `S=1 X=6` | `PyGObject`, `signals`, `module-api` | Signal matching, refcount, marshaller, and module-level APIs; one upstream bug-linked case remains skipped. |
| `test_signature.py` | `S=0 X=41` | `PyGObject`, `inspect.signature`, `callables` | `inspect.signature()` support for GI callables, methods, and vfuncs. |
| `test_source.py` | `S=0 X=18` | `PyGObject`, `GLib.Source`, `user-data` | GLib.Source subclassing and remaining `timeout_add` user-data and priority compatibility. |
| `test_subprocess.py` | `S=0 X=7` | `PyGObject`, `subprocess`, `GLib.spawn` | GLib subprocess helpers, `spawn_async` positional/keyword forms, and legacy aliases. |
| `test_thread.py` | `S=0 X=1` | `PyGObject`, `threading`, `hang-crash` | Thread compatibility case marked not-run because it hangs/crashes under ginext compatibility. |
| `test_typeclass.py` | `S=0 X=3` | `PyGObject`, `typeclass`, `coercion` | GObjectMeta/ObjectClass coercion and type-class property lookup. |
| `test_unknown.py` | `S=0 X=3` | `PyGObject`, `unknown`, `wrappers` | Unknown wrapper compatibility. |

### `signal/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_GObject_Object_gsignals.py` | `S=0 X=2` | `signals`, `GObject.Object`, `goi-port` | GObject signal compatibility from goi port, still pending adaptation. |
| `test_GObject_Object_signal.py` | `S=0 X=17` | `signals`, `GObject.Object`, `connect` | Legacy strict and user-data signal paths from goi port, still pending adaptation. |

### `typelib/`

| Module | Status | Tags | Exercises / blocker |
| --- | --- | --- | --- |
| `test_fundamental.py` | `S=0 X=16` | `typelib`, `fundamental`, `goi-port` | Fundamental type coverage against external typelibs; goi port remains pending. |
| `test_gi_marshalling_tests.py` | `S=1 X=0` | `typelib`, `callbacks`, `stateful-c` | `callback_owned_boxed` mutates static test-library state and breaks later PyGObject compatibility expectations in the same process. |

## Maintenance Notes

- When an `xfail(strict=False)` starts passing, remove or narrow the marker and
  update this file in the same change.
- When a skip is environment-only, keep the reason precise enough to explain how
  to enable it, for example installing cairo or using a debug CPython.
- When a backlog module is implemented, delete its row instead of leaving stale
  history here; git history is enough for old counts.
