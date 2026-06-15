host_is_windows = host_machine.system() == 'windows'

# Windows: provide a <dlfcn.h> shim (dlopen/dlsym/RTLD_DEFAULT) backed by
# LoadLibrary/GetProcAddress so the GI symbol resolution and cairo helpers work.
win32_sources = host_is_windows ? files('ginext/private/win32/dlfcn.c') : []
win32_includes = host_is_windows ? ['ginext/private/win32'] : []
win32_deps = host_is_windows ? [cc.find_library('psapi')] : []
# /FI force-includes the POSIX-compat header into every TU; FFI_STATIC_BUILD
# makes libffi's ffi_type_* plain externs (we link libffi statically on Windows),
# so taking their address in static initializers is a compile-time constant.
win32_cargs = host_is_windows ? ['/FIwin32-compat.h', '-DFFI_STATIC_BUILD'] : []

_gobject_ext = py.extension_module(
  '_gobject',
  win32_sources,
  files(
    'ginext/private/GObject/Object-class.c',
    'ginext/private/GObject/hooks.c',
    'ginext/private/GObject/Fundamental.c',
    'ginext/private/GObject/Type.c',
    'ginext/private/GObject/Value.c',
    'ginext/private/cairo/foreign.c',
    'ginext/private/GObject/ParamSpec-make.c',
    'ginext/private/GObject/Type-name.c',
    'ginext/private/GObject/GIMeta.c',
    'ginext/private/GObject/DeclaredProperty.c',
    'ginext/private/GObject/Object-register.c',
    'ginext/private/GObject/Object-vfunc.c',
    'ginext/private/GObject/Object-vfunc-wrapper.c',
    'ginext/private/GObject/Object-construct.c',
    'ginext/private/GObject/ObjectMeta.c',
    'ginext/private/GObject/Object-wrapper.c',
    'ginext/private/GObject/Object-unref.c',
    'ginext/private/GObject/Object-weakref.c',
    'ginext/private/GObject/Closure-record.c',
    'ginext/private/GObject/Closure-signal.c',
    'ginext/private/callable_descriptor.c',
    'ginext/private/namespace.c',
    'ginext/private/ginextmodule.c',
    'ginext/private/GObject/Object-info.c',
    'ginext/private/GLib/Array.c',
    'ginext/private/GLib/DateTime.c',
    'ginext/private/GLib/HashTable.c',
    'ginext/private/GLib/List.c',
    'ginext/private/GObject/coercions.c',
    'ginext/private/GLib/Variant.c',
    'ginext/private/GIRepository/Info.c',
    'ginext/private/GIRepository/BaseInfo.c',
    'ginext/private/GIRepository/CallableInfo.c',
    'ginext/private/GIRepository/FunctionInfo.c',
    'ginext/private/GIRepository/SignalInfo.c',
    'ginext/private/GIRepository/VFuncInfo.c',
    'ginext/private/GIRepository/CallbackInfo.c',
    'ginext/private/GIRepository/RegisteredTypeInfo.c',
    'ginext/private/GIRepository/ObjectInfo.c',
    'ginext/private/GIRepository/InterfaceInfo.c',
    'ginext/private/GIRepository/StructInfo.c',
    'ginext/private/GIRepository/UnionInfo.c',
    'ginext/private/GIRepository/EnumInfo.c',
    'ginext/private/GIRepository/FlagsInfo.c',
    'ginext/private/GIRepository/ConstantInfo.c',
    'ginext/private/GIRepository/PropertyInfo.c',
    'ginext/private/GIRepository/ArgInfo.c',
    'ginext/private/GIRepository/FieldInfo.c',
    'ginext/private/GIRepository/TypeInfo.c',
    'ginext/private/GIRepository/ValueInfo.c',
    'ginext/private/GIRepository/UnresolvedInfo.c',
    'ginext/private/GObject/Object-property.c',
    'ginext/private/GObject/Boxed.c',
    'ginext/private/GObject/Closure-callback.c',
    'ginext/private/GIRepository/Repository.c',
    'ginext/private/runtime/shims.c',
    'ginext/private/runtime/callable.c',
    'ginext/private/runtime/signal-api.c',
    'ginext/private/marshal/c-array.c',
    'ginext/private/marshal/container-element.c',
    'ginext/private/marshal/enum.c',
    'ginext/private/marshal/conversion.c',
    'ginext/private/marshal/gvalue.c',
    'ginext/private/marshal/pygi-value.c',
    'ginext/private/marshal/scalar.c',
    'ginext/private/marshal/string.c',
    'ginext/private/marshal/marshal.c',
    'ginext/private/invoke/arg-cleanup.c',
    'ginext/private/invoke/bind.c',
    'ginext/private/invoke/frame.c',
    'ginext/private/invoke/plan.c',
    'ginext/private/invoke/return.c',
    'ginext/private/invoke/ffi/invoke.c',
  ),
  dependencies : [ext_dep, gir, gobject, glib, dependency('gmodule-2.0'), libffi, threads, dependency('cairo')] + win32_deps,
  include_directories : include_directories('ginext/private',
                                            'ginext/private/GObject',
                                            win32_includes),
  c_args : win32_cargs,
  install : true,
  subdir : 'ginext/private',
)

_cairo_ext = py.extension_module(
  '_cairo',
  files('ginext/private/_cairo.c'),
  dependencies : [ext_dep, dependency('cairo-gobject')],
  install : true,
  subdir : 'ginext/private',
)

py.install_sources(
  'ginext/private/__init__.py',
  subdir : 'ginext/private',
)

copy_into = files(meson.project_source_root() / 'tools/meson/copy_into.py')

custom_target(
  'ginext_private__gobject_so',
  output : 'ginext_private__gobject_so.stamp',
  input : _gobject_ext,
  command : [py, copy_into, '@INPUT@', '@OUTDIR@/ginext/private', '@OUTPUT@'],
  build_by_default : true,
)

custom_target(
  'ginext_private__cairo_so',
  output : 'ginext_private__cairo_so.stamp',
  input : _cairo_ext,
  command : [py, copy_into, '@INPUT@', '@OUTDIR@/ginext/private', '@OUTPUT@'],
  build_by_default : true,
)

custom_target(
  'ginext_private___init___py',
  output : 'ginext_private___init___py.stamp',
  input : 'ginext/private/__init__.py',
  command : [py, copy_into, '@INPUT@', '@OUTDIR@/ginext/private', '@OUTPUT@'],
  build_by_default : true,
)

# ginext Python package: namespace-only experimental PyGI surface.
ginext_files = [
  ['ginext/__init__.py',   'ginext'],
  ['ginext/abi.py',        'ginext'],
  ['ginext/aio.py',        'ginext'],
  ['ginext/_aioloop.py',   'ginext'],
  ['ginext/cairo.py',      'ginext'],
  ['ginext/classbuild.py', 'ginext'],
  ['ginext/defaults.py',   'ginext'],
  ['ginext/enum.py',       'ginext'],
  ['ginext/features.py',   'ginext'],
  ['ginext/fundamental.py', 'ginext'],
  ['ginext/errors.py',     'ginext'],
  ['ginext/method.py',     'ginext'],
  ['ginext/namespace.py',  'ginext'],
  ['ginext/overlay/__init__.py',   'ginext/overlay'],
  ['ginext/overlay/bootstrap.py',  'ginext/overlay'],
  ['ginext/overlay/callbacks.py',  'ginext/overlay'],
  ['ginext/overlay/install.py',    'ginext/overlay'],
  ['ginext/overlay/registrar.py',  'ginext/overlay'],
  ['ginext/overlay/state.py',      'ginext/overlay'],
  ['ginext/overlay/types.py',      'ginext/overlay'],
  ['ginext/record.py',     'ginext'],
  ['ginext/runtime.py',    'ginext'],
  ['ginext/signature.py',  'ginext'],
  ['ginext/gobject/__init__.py', 'ginext/gobject'],
  ['ginext/gobject/resolve.py',  'ginext/gobject'],
  ['ginext/gobject/gtype.py',    'ginext/gobject'],
  ['ginext/gobject/properties.py', 'ginext/gobject'],
  ['ginext/gobject/metaclass.py', 'ginext/gobject'],
  ['ginext/gobject/subclass.py',  'ginext/gobject'],
  ['ginext/gobject/gobjectclass.py',     'ginext/gobject'],
  ['ginext/signal/__init__.py',   'ginext/signal'],
  ['ginext/signal/adapt.py',      'ginext/signal'],
  ['ginext/signal/scoped.py',     'ginext/signal'],
  ['ginext/signal/connection.py', 'ginext/signal'],
  ['ginext/signal/gtype.py',      'ginext/signal'],
  ['ginext/signal/bound.py',      'ginext/signal'],
  ['ginext/signal/descriptor.py', 'ginext/signal'],
  ['ginext/_overlays/__init__.py',        'ginext/_overlays'],
  ['ginext/_overlays/GIRepository.py',   'ginext/_overlays'],
  ['ginext/_overlays/GLib.py',           'ginext/_overlays'],
  ['ginext/_overlays/GObject.py',        'ginext/_overlays'],
]

foreach pair : ginext_files
  src_path = pair[0]
  rel_dir = pair[1]
  tag = src_path.replace('/', '_').replace('.', '_')
  custom_target(
    'ginext_' + tag,
    output : tag + '.stamp',
    input : src_path,
    command : [py, copy_into, '@INPUT@', '@OUTDIR@/' + rel_dir, '@OUTPUT@'],
    build_by_default : true,
  )
  install_data(
    src_path,
    install_dir : py.get_install_dir() / rel_dir,
  )
endforeach

# gi compat package — keep the build directory in sync so PYTHONPATH picks up
# the latest sources rather than stale copies from old builds.
gi_files = [
  ['../packages/ginext-gi-compat/src/gi/__init__.py',         'gi'],
  ['../packages/ginext-gi-compat/src/gi/_constants.py',       'gi'],
  ['../packages/ginext-gi-compat/src/gi/_error.py',           'gi'],
  ['../packages/ginext-gi-compat/src/gi/_compat_namespace.py', 'gi'],
  ['../packages/ginext-gi-compat/src/gi/_gi.py',              'gi'],
  ['../packages/ginext-gi-compat/src/gi/_gtype_compat.py',    'gi'],
  ['../packages/ginext-gi-compat/src/gi/_gobject_compat_methods.py', 'gi'],
  ['../packages/ginext-gi-compat/src/gi/_gobject_props.py',  'gi'],
  ['../packages/ginext-gi-compat/src/gi/_gtktemplate.py',     'gi'],
  ['../packages/ginext-gi-compat/src/gi/_gtk_treemodel.py',  'gi'],
  ['../packages/ginext-gi-compat/src/gi/_ossighelper.py',     'gi'],
  ['../packages/ginext-gi-compat/src/gi/_propertyhelper.py',  'gi'],
  ['../packages/ginext-gi-compat/src/gi/_repository_helpers.py', 'gi'],
  ['../packages/ginext-gi-compat/src/gi/_signalhelper.py',    'gi'],
  ['../packages/ginext-gi-compat/src/gi/docstring.py',        'gi'],
  ['../packages/ginext-gi-compat/src/gi/events.py',           'gi'],
  ['../packages/ginext-gi-compat/src/gi/importer.py',         'gi'],
  ['../packages/ginext-gi-compat/src/gi/module.py',           'gi'],
  ['../packages/ginext-gi-compat/src/gi/repository.py',       'gi'],
  ['../packages/ginext-gi-compat/src/gi/types.py',            'gi'],
  ['../packages/ginext-gi-compat/src/gi/overrides/__init__.py',            'gi/overrides'],
  ['../packages/ginext-gi-compat/src/gi/overrides/Gio.py',                'gi/overrides'],
  ['../packages/ginext-gi-compat/src/gi/overrides/Gtk.py',                'gi/overrides'],
  ['../packages/ginext-gi-compat/src/gi/overrides/GIMarshallingTests.py', 'gi/overrides'],
  ['../packages/ginext-gi-compat/src/gi/overrides/GLib.py',              'gi/overrides'],
  ['../packages/ginext-gi-compat/src/gi/overrides/GObject.py',           'gi/overrides'],
  ['../packages/ginext-gi-compat/src/gi/overrides/Pango.py',             'gi/overrides'],
  ['../packages/ginext-gi-compat/src/gi/overrides/Gdk.py',               'gi/overrides'],
]

foreach pair : gi_files
  src_path = pair[0]
  rel_dir = pair[1]
  tag = 'gi_' + src_path.replace('../packages/ginext-gi-compat/src/gi/', '').replace('/', '_').replace('.', '_')
  custom_target(
    tag,
    output : tag + '.stamp',
    input : src_path,
    command : [py, copy_into, '@INPUT@', '@OUTDIR@/' + rel_dir, '@OUTPUT@'],
    build_by_default : true,
  )
endforeach

custom_target(
  'pygobject_testhelper_py',
  output : 'pygobject_testhelper_py.stamp',
  input : 'testhelper.py',
  command : [py, copy_into, '@INPUT@', '@OUTDIR@', '@OUTPUT@'],
  build_by_default : true,
)
install_data(
  'testhelper.py',
  install_dir : py.get_install_dir(),
)
