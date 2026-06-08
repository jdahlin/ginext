gnome = import('gnome')

gio = dependency('gio-2.0')
cairo = dependency('cairo')
cairo_gobject = dependency('cairo-gobject')

typelib_cc = meson.get_compiler('c')
typelib_compile_args = typelib_cc.get_supported_arguments(['-Wno-unused-parameter'])

if host_machine.system() == 'windows'
  gi_test_extern = '__declspec(dllexport) extern'
else
  gi_test_extern = '__attribute__((visibility("default"))) extern'
endif
typelib_compile_args += ['-DGI_TEST_EXTERN=' + gi_test_extern]

typelib_inc = include_directories('.')

utility_sources = files('utility.c', 'utility.h')
regress_sources = files(
  'annotation.c',
  'annotation.h',
  'drawable.c',
  'drawable.h',
  'foo.c',
  'foo.h',
  'regress.c',
  'regress.h',
  'regressextra.c',
  'regressextra.h',
)
regress_unix_sources = files('regress-unix.c', 'regress-unix.h')
gimarshallingtests_sources = files(
  'gimarshallingtests.c',
  'gimarshallingtests.h',
  'gimarshallingtestsextra.c',
  'gimarshallingtestsextra.h',
)
goi_bench_sources = files('bench.c', 'bench.h')

libutility = library(
  'utility',
  utility_sources,
  c_args : typelib_compile_args,
  dependencies : [glib, gobject],
  gnu_symbol_visibility : 'hidden',
  install : false,
)
utility_gir = gnome.generate_gir(
  libutility,
  sources : utility_sources,
  namespace : 'Utility',
  nsversion : '1.0',
  symbol_prefix : 'utility_',
  header : 'utility.h',
  includes : ['GObject-2.0'],
  fatal_warnings : true,
  install_gir : false,
  install_typelib : false,
)

libregress = library(
  'regress',
  regress_sources + regress_unix_sources,
  c_args : typelib_compile_args,
  include_directories : typelib_inc,
  dependencies : [glib, gobject, gio, cairo, cairo_gobject],
  gnu_symbol_visibility : 'hidden',
  install : false,
  override_options : ['unity=off'],
)
regress_gir = gnome.generate_gir(
  libregress,
  sources : regress_sources,
  namespace : 'Regress',
  nsversion : '1.0',
  identifier_prefix : 'Regress',
  symbol_prefix : 'regress_',
  header : 'regress.h',
  includes : ['Gio-2.0', 'cairo-1.0', utility_gir[0]],
  extra_args : ['--warn-all'],
  include_directories : typelib_inc,
  fatal_warnings : true,
  install_gir : false,
  install_typelib : false,
)

if host_machine.system() != 'windows'
  regress_unix_gir = gnome.generate_gir(
    libregress,
    sources : regress_unix_sources,
    namespace : 'RegressUnix',
    nsversion : '1.0',
    symbol_prefix : 'regress_unix_',
    header : 'regress-unix.h',
    includes : ['Gio-2.0', 'cairo-1.0', utility_gir[0]],
    include_directories : typelib_inc,
    fatal_warnings : true,
    install_gir : false,
    install_typelib : false,
  )
else
  regress_unix_gir = [disabler(), disabler()]
endif

libgimarshallingtests = library(
  'gimarshallingtests',
  gimarshallingtests_sources,
  c_args : typelib_compile_args,
  dependencies : [glib, gobject, gio],
  gnu_symbol_visibility : 'hidden',
  install : false,
)
gimarshallingtests_gir = gnome.generate_gir(
  libgimarshallingtests,
  sources : gimarshallingtests_sources,
  namespace : 'GIMarshallingTests',
  nsversion : '1.0',
  symbol_prefix : 'gi_marshalling_tests_',
  includes : ['Gio-2.0'],
  fatal_warnings : true,
  install_gir : false,
  install_typelib : false,
)

libgoibench = shared_library(
  'goibench',
  goi_bench_sources,
  dependencies : [glib, gobject],
  install : false,
)
goibench_gir = gnome.generate_gir(
  libgoibench,
  sources : goi_bench_sources,
  namespace : 'GoiBench',
  nsversion : '1.0',
  identifier_prefix : 'GoiBench',
  symbol_prefix : 'goi_bench_',
  header : 'bench.h',
  includes : ['GObject-2.0'],
  install_gir : false,
  install_typelib : false,
)

typelib_stub_outputs = [
  'GIMarshallingTests.pyi',
  'GoiBench.pyi',
  'Regress.pyi',
  'RegressUnix.pyi',
  'Utility.pyi',
  '__init__.pyi',
  'py.typed',
]
typelib_stubs = custom_target(
  'typelib-native-stubs',
  output : typelib_stub_outputs,
  depends : [
    utility_gir[0],
    regress_gir[0],
    regress_unix_gir[0],
    gimarshallingtests_gir[0],
    goibench_gir[0],
  ],
  env : {
    'GOI_GIR_DIR' : meson.current_build_dir(),
  },
  command : [
    py,
    meson.current_source_dir() / 'generate_stubs.py',
    '@OUTDIR@',
    'Utility:1.0',
    'Regress:1.0',
    'RegressUnix:1.0',
    'GIMarshallingTests:1.0',
    'GoiBench:1.0',
  ],
  build_by_default : true,
  install : true,
  install_dir : py.get_install_dir() / 'ginext',
)
