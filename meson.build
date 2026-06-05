project(
  'goi',
  'c',
  version : '0.0.1',
  default_options : [
    'c_std=c11',
    'warning_level=2',
    'werror=true',
    'b_ndebug=if-release',
    # Default to debugoptimized so perf gets useful symbols. Override at the
    # meson cmdline (-Dbuildtype=release) for a true release build.
    'buildtype=debugoptimized',
  ],
)

cc = meson.get_compiler('c')
add_project_arguments(
  cc.get_supported_arguments([
    '-Wno-error=stringop-overflow',
    '-Wno-stringop-overflow',
  ]),
  language : 'c',
)

# Toolchain: libgirepository-2.0 + glib + gobject. libffi is for
# closure-in (signal handlers / vfunc callbacks); never on the call-out path.
py        = import('python').find_installation(pure : false)
gir       = dependency('girepository-2.0', version : '>=2.80')
gobject   = dependency('gobject-2.0')
glib      = dependency('glib-2.0')
libffi    = dependency('libffi')
threads   = dependency('threads')

profiling_args = cc.get_supported_arguments([
  '-fno-omit-frame-pointer',
  '-mno-omit-leaf-frame-pointer',
])
# _GNU_SOURCE on the command line so glibc exposes strdup / strndup /
# RTLD_DEFAULT to every TU regardless of include order.
ext_compile_args = cc.get_supported_arguments([
  '-Wno-unused-parameter',
]) + ['-D_GNU_SOURCE'] + profiling_args
ext_link_args = []
# Sanitize the extension only (not the introspection-scanned test typelibs):
# g-ir-scanner links a temporary binary, and under the global b_sanitize that
# link pulls in the GNU runtime soname (-lasan), which Apple clang cannot find.
ginext_sanitize = get_option('ginext_sanitize')
if ginext_sanitize != ''
  sanitize_args = ['-fsanitize=' + ginext_sanitize]
  ext_compile_args += sanitize_args
  ext_link_args += sanitize_args
endif
ext_dep = declare_dependency(
  compile_args : ext_compile_args,
  link_args : ext_link_args,
)

subdir('src')

# ---------------------------------------------------------------------------
# Test typelibs live under packages/typelib.
# Built only when -Dbuild_gi_tests=true, so a normal release build of goi
# doesn't pay the compile time. The pytest harness points GI_TYPELIB_PATH and
# LD_LIBRARY_PATH at the package build dir.
# ---------------------------------------------------------------------------
if get_option('build_gi_tests')
  subdir('packages/typelib')
  message('test typelibs will be in: packages/typelib')
endif
