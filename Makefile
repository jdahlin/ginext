PYTHON       ?= cpython-3.14t
PYTHON_ENV_NAME ?= $(PYTHON)
PYGIR_TEST_PYTHON_GIL ?=
# Debug interpreter for `make *-debug`. python-build-standalone ships a debug
# build per platform; match the freethreaded default on macOS.
ifeq ($(shell uname),Darwin)
DEBUG_PYTHON := cpython-3.14.4+freethreaded+debug-macos-aarch64-none
else
DEBUG_PYTHON := cpython-3.14.3+debug-linux-x86_64-gnu
endif
# Empty by default so `make test` collects the full testpaths (every non-gst
# package) in one pytest invocation. Set it to scope a run, e.g.
# PYTEST_ARGS=src/ginext/tests/foo.py.
PYTEST_ARGS  ?=
PYTEST_MARK  ?= not gtk3
PYTEST_ENV   ?=
# Single worker-count knob for all variants (test, asan, ubsan, debug). 5 (not
# -n auto): the suite is contention-bound — the free-threaded GObject type system
# serialises on shared locks — so per-invocation throughput is near its peak well
# below core count, and keeping it modest leaves headroom to run several test
# phases / invocations in parallel without saturating the box (and spinning up the
# fans). Override with e.g. PYTEST_WORKERS=12 or PYTEST_XDIST_ARGS='-n auto'.
PYTEST_WORKERS ?= 5
PYTEST_XDIST_ARGS ?= -n $(PYTEST_WORKERS) --max-worker-restart=0
PYTEST_TIMEOUT ?= 10
PYTEST_HANG_ARGS ?= -o faulthandler_timeout=$(PYTEST_TIMEOUT) -o faulthandler_exit_on_timeout=true
PYTEST_JUNIT_DIR ?=
DEBUG_PYTEST_WORKERS ?= $(PYTEST_WORKERS)
DEBUG_PYTEST_ARGS ?= -n $(DEBUG_PYTEST_WORKERS) --max-worker-restart=0
GTK3_PYTEST_ARGS ?= -n 0
BUILD_ENV ?=
CCACHE_DISABLE ?=
CI_IMAGE ?= ghcr.io/jdahlin/ginext-ci:debian-testing
CI_DOCKERFILE ?= ci/Dockerfile

_P     := $(subst /,-,$(subst +,-,$(PYTHON_ENV_NAME)))
VENV   := .venv-$(_P)
BDIR   := build/$(_P)
GI_TESTS_BDIR := $(abspath $(BDIR)/packages/typelib)
UV     := uv
PY     := $(abspath $(VENV)/bin/python3)
PYTEST := $(abspath $(VENV)/bin/pytest)
# Always run uv-managed tools against THIS project's venv ($(VENV)), never uv's
# implicit ./.venv. Without this, `uv run mypy` can pick up a stale or
# differently-versioned ./.venv that lacks the freshly generated/installed
# ginext-stubs, so the GI namespace stubs resolve to Any. Absolute path so it
# survives `uv run --directory`.
UV_RUN := env UV_PROJECT_ENVIRONMENT=$(abspath $(VENV)) $(UV) run
# Runtime invocations go through RUN_PY/RUN_PYTEST so wrappers (gdb,
# valgrind, etc.) can override these without leaking the wrap into the
# build/meson-setup phase, which needs the bare interpreter path.
RUN_PY     := $(PY)
RUN_PYTEST := $(PYTEST)
NINJA  := $(shell command -v ninja 2>/dev/null || echo /usr/bin/ninja)
MESON  := $(shell command -v meson 2>/dev/null || echo /usr/bin/meson)
CACHE  := XDG_CACHE_HOME=/tmp/pygir-cache
# On macOS the GIR/typelib data installed by Homebrew lives under its prefix,
# which is not in the default XDG_DATA_DIRS. g-ir-compiler needs it to resolve
# base GIRs (GObject, Gio, ...) referenced by the test typelibs.
_BREW_PREFIX := $(shell command -v brew >/dev/null 2>&1 && brew --prefix 2>/dev/null)
_XDG_DATA := $(if $(_BREW_PREFIX),XDG_DATA_DIRS=$(_BREW_PREFIX)/share$${XDG_DATA_DIRS:+:$$XDG_DATA_DIRS})
_CCACHE_DISABLE := $(if $(CCACHE_DISABLE),CCACHE_DISABLE=$(CCACHE_DISABLE))
MESON_SETUP_ARGS ?= -Dbuild_gi_tests=true
_PACKAGES_PYTHONPATH := $(abspath packages/ginext-gio/src):$(abspath packages/ginext-gtk/src):$(abspath packages/ginext-gi-compat/src):$(abspath packages/ginext-gst/src)
# macOS uses DYLD_LIBRARY_PATH instead of LD_LIBRARY_PATH. The GI typelib loader
# dlopen()s libraries by leaf name, so both the in-tree test typelib dylibs and
# the Homebrew-installed glib/gtk dylibs must be reachable at runtime.
_DYLD  := $(if $(filter Darwin,$(shell uname)),DYLD_LIBRARY_PATH=$(GI_TESTS_BDIR)$(if $(_BREW_PREFIX),:$(_BREW_PREFIX)/lib)$${DYLD_LIBRARY_PATH:+:$$DYLD_LIBRARY_PATH})
_ENV   := PYTHONPATH=$(abspath $(BDIR)/src):$(_PACKAGES_PYTHONPATH) PYGIR_GI_TESTS_BUILDDIR=$(GI_TESTS_BDIR) GOI_BENCH_BUILDDIR=$(GI_TESTS_BDIR) GI_TYPELIB_PATH=$(GI_TESTS_BDIR)$${GI_TYPELIB_PATH:+:$$GI_TYPELIB_PATH} LD_LIBRARY_PATH=$(GI_TESTS_BDIR)$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH} $(_DYLD)
_MALLOC := $(if $(findstring debug,$(_P)),MALLOC_CHECK_=3 MALLOC_PERTURB_=45)
_TEST_GIL := $(if $(PYGIR_TEST_PYTHON_GIL),PYTHON_GIL=$(PYGIR_TEST_PYTHON_GIL))
_JUNIT_SETUP := $(if $(PYTEST_JUNIT_DIR),mkdir -p $(PYTEST_JUNIT_DIR) &&)
_JUNIT_NOT_GTK3 := $(if $(PYTEST_JUNIT_DIR),--junitxml=$(PYTEST_JUNIT_DIR)/not-gtk3.xml)
_JUNIT_GIO := $(if $(PYTEST_JUNIT_DIR),--junitxml=$(PYTEST_JUNIT_DIR)/ginext-gio.xml)
_JUNIT_GTK3 := $(if $(PYTEST_JUNIT_DIR),--junitxml=$(PYTEST_JUNIT_DIR)/gtk3.xml)
_JUNIT_GTK4 := $(if $(PYTEST_JUNIT_DIR),--junitxml=$(PYTEST_JUNIT_DIR)/gtk4.xml)
_JUNIT_GI_COMPAT := $(if $(PYTEST_JUNIT_DIR),--junitxml=$(PYTEST_JUNIT_DIR)/gi-compat.xml)
_JUNIT_GST := $(if $(PYTEST_JUNIT_DIR),--junitxml=$(PYTEST_JUNIT_DIR)/ginext-gst.xml)

VALGRIND      := /usr/bin/valgrind
VALGRIND_LOG  := /tmp/pygir-valgrind.log
VALGRIND_FLAGS := \
    --tool=memcheck --leak-check=full --show-leak-kinds=definite \
    --num-callers=20 --error-exitcode=1 \
    --suppressions=/usr/lib/valgrind/python3.supp \
    --suppressions=/usr/share/glib-2.0/valgrind/glib.supp \
    --suppressions=/usr/share/gtk-4.0/valgrind/gtk.supp \
    --suppressions=$(abspath pygobject/tools/pygobject.supp) \
    --suppressions=$(abspath pygobject/tests/valgrind.supp) \
    --log-file=$(VALGRIND_LOG)

SANITIZE ?= address,undefined
SANITIZER_PYTHON ?= $(DEBUG_PYTHON)
SANITIZER_SUFFIX ?= sanitize
SANITIZER_G_DEBUG ?= gc-friendly
SANITIZER_G_SLICE ?= always-malloc
SANITIZER_EXTRA_ENV ?=
SANITIZER_PYTEST_ARGS ?=
# Combined asan+ubsan (the default SANITIZE) is the heaviest on memory, so it
# stays serial; the single-sanitizer variants use the shared PYTEST_WORKERS count.
SANITIZER_PYTEST_XDIST_ARGS ?= -n 0
ASAN_PYTEST_XDIST_ARGS ?= -n $(PYTEST_WORKERS) --max-worker-restart=0
UBSAN_PYTEST_XDIST_ARGS ?= -n $(PYTEST_WORKERS) --max-worker-restart=0
SANITIZER_PYTEST_TIMEOUT ?= 60
SANITIZER_PYTEST_HANG_ARGS ?= -o faulthandler_timeout=$(SANITIZER_PYTEST_TIMEOUT) -o faulthandler_exit_on_timeout=true
SANITIZER_TEST_TARGET ?= test
ASAN_OPTIONS ?= abort_on_error=1:detect_leaks=0:strict_string_checks=1:malloc_context_size=50:print_stacktrace=1
UBSAN_OPTIONS ?= halt_on_error=1:print_stacktrace=1
_SANITIZER_P := $(subst /,-,$(subst +,-,$(SANITIZER_PYTHON)))
# Build-side (what gets sanitized) lives in meson; the Makefile only owns how
# the test process is launched. The two platforms differ in three ways:
# meson knob, how the runtime is preloaded, and PYTHONMALLOC.
ifeq ($(shell uname),Darwin)
# Instrument only the ginext extension (-Dginext_sanitize) so the test typelibs
# stay uninstrumented — the global b_sanitize makes g-ir-scanner link -lasan,
# which Apple clang cannot resolve. Load the clang_rt runtime via
# DYLD_INSERT_LIBRARIES (dyld ignores LD_PRELOAD) and skip PYTHONMALLOC=malloc,
# which the freethreaded interpreter rejects.
_SANITIZE_MESON_ARG = -Dginext_sanitize=$(SANITIZE)
# pytest-xdist workers crash at spawn under asan on macOS (the runtime's
# startup disrupts execnet's worker pipe handshake), so run asan serially.
ASAN_PYTEST_XDIST_ARGS := -n 0
_ASAN_RUNTIME := $(if $(findstring address,$(SANITIZE)),$(shell $(CC) -print-file-name=libclang_rt.asan_osx_dynamic.dylib))
_SANITIZER_PRELOAD_ENV = $(if $(_ASAN_RUNTIME),DYLD_INSERT_LIBRARIES=$(_ASAN_RUNTIME)$${DYLD_INSERT_LIBRARIES:+:$$DYLD_INSERT_LIBRARIES})
_SANITIZER_BUILD_PRELOAD_ENV =
# asan strips DYLD_INSERT_LIBRARIES from the environment after its startup
# re-exec, so the subprocess-marker child would load the instrumented extension
# without the runtime preloaded. Stash the path in a var asan leaves alone;
# conftest restores DYLD_INSERT_LIBRARIES for the child from it.
_SANITIZER_SUBPROC_ENV = $(if $(_ASAN_RUNTIME),PYGIR_ASAN_RUNTIME=$(_ASAN_RUNTIME))
SANITIZER_ENV = G_DEBUG=$(SANITIZER_G_DEBUG) G_SLICE=$(SANITIZER_G_SLICE) ASAN_OPTIONS=$(ASAN_OPTIONS) UBSAN_OPTIONS=$(UBSAN_OPTIONS) $(_SANITIZER_PRELOAD_ENV) $(_SANITIZER_SUBPROC_ENV) $(SANITIZER_EXTRA_ENV)
else
SANITIZER_LD_PRELOAD ?= $(if $(findstring address,$(SANITIZE)),$(shell $(CC) -print-file-name=libasan.so))
_SANITIZE_MESON_ARG = -Db_sanitize=$(SANITIZE)
_SANITIZER_PRELOAD_ENV = $(if $(SANITIZER_LD_PRELOAD),LD_PRELOAD=$(SANITIZER_LD_PRELOAD)$${LD_PRELOAD:+:$$LD_PRELOAD})
_SANITIZER_BUILD_PRELOAD_ENV = $(_SANITIZER_PRELOAD_ENV)
SANITIZER_ENV = PYTHONMALLOC=malloc G_DEBUG=$(SANITIZER_G_DEBUG) G_SLICE=$(SANITIZER_G_SLICE) ASAN_OPTIONS=$(ASAN_OPTIONS) UBSAN_OPTIONS=$(UBSAN_OPTIONS) $(_SANITIZER_PRELOAD_ENV) $(SANITIZER_EXTRA_ENV)
endif

GCOVR      := gcovr
GCOVR_ARGS := --root $(CURDIR) --object-directory $(BDIR) --filter $(abspath src/goi/_goi) --txt

.PHONY: venv setup build release docker-image docker-image-push test test-not-gtk3 test-gtk3 test-gtk4 _test-not-gtk3 _test-gtk3 test-ginext-gio test-ginext-gtk test-ginext-gi-compat test-ginext-gst test-sanitize test-asan test-ubsan test-coverage tox tox-release run profile valgrind clean showtime drawing pyedit text-editor web-browser terminal gnome-music cambalache quodlibet coverage-report docviewer typecheck _typecheck-core _typecheck-gio _typecheck-gtk _typecheck-gst _typecheck-stubgen _typecheck-commander stubs

$(VENV)/.pygir-sync-stamp: pyproject.toml uv.lock \
    packages/ginext-gio/pyproject.toml \
    packages/ginext-gtk/pyproject.toml \
    packages/ginext-gi-compat/pyproject.toml \
    packages/ginext-gst/pyproject.toml
	@UV_PROJECT_ENVIRONMENT=$(VENV) $(UV) sync --python $(PYTHON) --no-install-project
	@$(UV) pip install --quiet --python $(PY) --no-deps \
	    -e packages/ginext-gio \
	    -e packages/ginext-gtk \
	    -e packages/ginext-gi-compat \
	    -e packages/ginext-gst
	@touch $@

venv: $(VENV)/.pygir-sync-stamp

setup: venv
	@mkdir -p $(BDIR)
	@printf '[binaries]\npython = '"'"'$(PY)'"'"'\n' > $(BDIR)/native.ini
	@if [ -f $(BDIR)/build.ninja ]; then \
		$(MESON) setup --reconfigure --native-file $(BDIR)/native.ini $(MESON_SETUP_ARGS) $(BDIR) > /dev/null; \
	else \
		$(MESON) setup --native-file $(BDIR)/native.ini $(MESON_SETUP_ARGS) $(BDIR) > /dev/null; \
	fi

build: setup
	@$(BUILD_ENV) $(_CCACHE_DISABLE) $(CACHE) $(_XDG_DATA) $(NINJA) --quiet -C $(BDIR)

release:
	@$(MAKE) build BDIR=build/release MESON_SETUP_ARGS='-Dbuild_gi_tests=true -Dbuildtype=release'

docker-image:
	docker build -t $(CI_IMAGE) -f $(CI_DOCKERFILE) .

docker-image-push: docker-image
	docker push $(CI_IMAGE)

# One pytest invocation over the full (non-gst) testpaths instead of a phase per
# package, so workers spin up once. gtk3 runs in its own Gtk:3.0 subprocess (see
# test_gtk3_subprocess.py), so this covers gtk3+gtk4 too. gst stays a second
# invocation: its overlay's ctypes GType capture contaminates the shared GObject
# type system when it shares a worker (see work.md). test-asan / test-ubsan /
# test-debug inherit this by running `test`. The per-package targets below remain
# for granular runs.
# One pytest invocation over the full (non-gtk3) testpaths — gst included, now
# that its GValue fallback no longer contaminates the shared GType view (see the
# ginext_gst._gstvalue C extension). gtk3 still runs in its own Gtk:3.0
# subprocess (driven from within the suite). `make test-ginext-gst` stays as a
# standalone target for gst-only runs.
test: build _test-not-gtk3

test-not-gtk3: build _test-not-gtk3

test-gtk3: build _test-gtk3

test-gtk4: test-not-gtk3

_test-not-gtk3:
	@$(_JUNIT_SETUP) $(_MALLOC) $(_ENV) $(PYTEST_ENV) $(_TEST_GIL) $(RUN_PYTEST) -m "$(PYTEST_MARK)" $(PYTEST_XDIST_ARGS) $(PYTEST_HANG_ARGS) $(_JUNIT_NOT_GTK3) $(PYTEST_ARGS)

_test-gtk3:
	@$(_JUNIT_SETUP) $(_MALLOC) $(_ENV) GINEXT_VERSIONS=Gtk:3.0 $(PYTEST_ENV) $(_TEST_GIL) $(RUN_PYTEST) -m gtk3 $(PYTEST_HANG_ARGS) $(_JUNIT_GTK3) $(PYTEST_ARGS) $(GTK3_PYTEST_ARGS) || { status=$$?; [ $$status -eq 5 ]; }

test-ginext-gio: build
	@$(_JUNIT_SETUP) $(_MALLOC) $(_ENV) $(PYTEST_ENV) $(_TEST_GIL) $(RUN_PYTEST) \
		--rootdir=packages/ginext-gio $(_JUNIT_GIO) packages/ginext-gio/tests/

test-ginext-gi-compat: build
	@$(_JUNIT_SETUP) $(_MALLOC) $(_ENV) $(PYTEST_ENV) $(_TEST_GIL) $(RUN_PYTEST) \
		--rootdir=packages/ginext-gi-compat $(_JUNIT_GI_COMPAT) packages/ginext-gi-compat/tests/

test-ginext-gst: build
	@$(_JUNIT_SETUP) $(_MALLOC) $(_ENV) $(PYTEST_ENV) $(_TEST_GIL) $(RUN_PYTEST) \
		--rootdir=packages/ginext-gst $(PYTEST_XDIST_ARGS) $(PYTEST_HANG_ARGS) \
		$(_JUNIT_GST) $(PYTEST_ARGS) packages/ginext-gst/tests/

test-ginext-gtk: build
	@$(_JUNIT_SETUP) $(_MALLOC) $(_ENV) GINEXT_VERSIONS=Gtk:3.0 $(PYTEST_ENV) $(_TEST_GIL) $(RUN_PYTEST) \
		--rootdir=packages/ginext-gtk $(PYTEST_HANG_ARGS) $(_JUNIT_GTK3) \
		packages/ginext-gtk/tests/gtk3/ $(GTK3_PYTEST_ARGS) || { s=$$?; [ $$s -eq 5 ]; }
	@$(_JUNIT_SETUP) $(_MALLOC) $(_ENV) $(PYTEST_ENV) $(_TEST_GIL) $(RUN_PYTEST) \
		--rootdir=packages/ginext-gtk $(PYTEST_HANG_ARGS) $(_JUNIT_GTK4) \
		packages/ginext-gtk/tests/gtk4/ \
		packages/ginext-gtk/tests/pango/ \
		packages/ginext-gtk/tests/gdk/ \
		packages/ginext-gtk/tests/gsk/ || { s=$$?; [ $$s -eq 5 ]; }

tox:
	$(UV) run tox run-parallel

tox-release:
	$(UV) run tox run-parallel -m release

# --- Generated type stubs (.pyi) ---------------------------------------------
# The .pyi stubs are derived solely from: the stubgen package itself, the
# runtime overlays it statically harvests (src/ginext/_overlays/*.py), and the
# in-repo test-typelib GIRs it reads. System GIRs (/usr/share/gir-1.0) are
# intentionally not listed — they only change on a distro upgrade, which
# rebuilds the CI image. "generate" is split from "install" so the expensive
# GIR parsing is gated by a content stamp (cacheable in CI), while the cheap
# reinstall-into-venv is gated separately on the venv stamp — a fresh venv must
# always have ginext-stubs (re)installed for mypy's PEP 561 stub discovery.
STUB_PKG_ROOT      := packages/ginext-stubs
STUB_GEN_STAMP     := $(STUB_PKG_ROOT)/.stub-generated.stamp
STUB_INSTALL_STAMP := $(VENV)/.ginext-stubs-installed
STUBGEN_SRC        := $(wildcard packages/ginext-stubgen/src/ginext_stubgen/*.py) \
                      $(wildcard packages/ginext-stubgen/src/ginext_stubgen/*.toml)
STUB_OVERLAYS      := $(wildcard src/ginext/_overlays/*.py) \
                      $(wildcard src/ginext/_overlays/*.toml)
STUB_TEST_GIRS     := $(wildcard $(GI_TESTS_BDIR)/*.gir)

$(STUB_GEN_STAMP): $(STUBGEN_SRC) $(STUB_OVERLAYS) $(STUB_TEST_GIRS) | venv
	$(UV_RUN) ginext-stubgen generate-all
	@touch $@

$(STUB_INSTALL_STAMP): $(STUB_GEN_STAMP) $(VENV)/.pygir-sync-stamp
	$(UV) pip install --quiet --python $(PY) --no-deps --reinstall $(STUB_PKG_ROOT)
	@touch $@

stubs: $(STUB_INSTALL_STAMP)

# Run the per-project mypy invocations concurrently (recursive make -j, so it's
# parallel by default — no need to pass -j on the command line). Each invocation
# is self-contained and green on its own; splitting just parallelizes wall-clock.
# Each gets its own incremental cache dir — parallel runs sharing one
# .mypy_cache corrupt each other, since the same module name resolves
# differently per package. ci/run-mypy.sh self-heals the cache: mypy 2.1 can
# INTERNAL-ERROR on a stale cache (e.g. CI's restored .mypy_cache from another
# commit), so it wipes the dir and retries once — incremental speed, no crash.
typecheck: stubs
	+$(MAKE) --no-print-directory -j _typecheck-core _typecheck-gio _typecheck-gtk _typecheck-gst _typecheck-stubgen _typecheck-commander

_typecheck-core:
	bash ci/run-mypy.sh .mypy_cache/core $(UV_RUN) mypy --strict src/ginext/ scripts/
_typecheck-gio:
	bash ci/run-mypy.sh .mypy_cache/gio $(UV_RUN) mypy --strict packages/ginext-gio/
_typecheck-gtk:
	bash ci/run-mypy.sh .mypy_cache/gtk $(UV_RUN) mypy --strict packages/ginext-gtk/
_typecheck-gst:
	bash ci/run-mypy.sh .mypy_cache/gst $(UV_RUN) mypy --strict packages/ginext-gst/
_typecheck-stubgen:
	bash ci/run-mypy.sh .mypy_cache/stubgen $(UV_RUN) mypy --strict packages/ginext-stubgen/
_typecheck-commander:
	bash ci/run-mypy.sh examples/commander/.mypy_cache $(UV_RUN) --directory examples/commander mypy --strict src/commander

run: build
	$(_ENV) $(RUN_PY) examples/mandelbrot/app.py

# Documentation viewer prototype — renders a Markdown file in a
# GtkTextView and embeds runnable example snippets via Casilda.
DOC ?= tools/docviewer/example.md
docviewer: build
	$(_ENV) $(RUN_PY) tools/docviewer/docviewer.py $(DOC)

# Drawing (https://github.com/maoschanz/drawing) lives in apps/drawing-run.
# Real-app integration target — exercises GtkApplication, ActionMap,
# Gtk.Template, GResource, GSettings, Cairo. The schemas dir holds the
# compiled gschemas for `com.github.maoschanz.drawing.*` so the app
# doesn't need a system install. PYTHONPATH adds the pygir build dir
# (which ships gir/) so the launcher's `import gir; gir.install_as_gi()`
# resolves to pygir and not system PyGObject.
# Showtime (https://gitlab.gnome.org/GNOME/showtime) lives in apps/showtime.
# Real-app integration target — exercises GtkApplication, GStreamer, GTK4,
# libadwaita, GSettings, blueprint-compiled GResources.
# Meson installs to a local prefix inside the source tree so no system install
# is needed. A -c preamble installs gir as gi via gir.install_as_gi() before
# showtime's own modules run; PYTHONPATH adds the pygir build dir so gir/
# is importable from there.
SHOWTIME_DIR    := $(abspath apps/showtime)
SHOWTIME_BDIR   := $(SHOWTIME_DIR)/_build
SHOWTIME_PREFIX := $(SHOWTIME_DIR)/_install

showtime: build
	@mkdir -p $(SHOWTIME_BDIR)
	@if [ -f $(SHOWTIME_BDIR)/build.ninja ]; then \
		$(MESON) setup --reconfigure --prefix=$(SHOWTIME_PREFIX) \
			-Dprofile=development \
			-Dpython_exec=$(PY) \
			$(SHOWTIME_BDIR) $(SHOWTIME_DIR) > /dev/null; \
	else \
		$(MESON) setup --prefix=$(SHOWTIME_PREFIX) \
			-Dprofile=development \
			-Dpython_exec=$(PY) \
			$(SHOWTIME_BDIR) $(SHOWTIME_DIR) > /dev/null; \
	fi
	@$(NINJA) --quiet -C $(SHOWTIME_BDIR) install
	@GSETTINGS_SCHEMA_DIR=$(SHOWTIME_PREFIX)/share/glib-2.0/schemas \
	PYTHONPATH=$(abspath $(BDIR)/src):$(SHOWTIME_PREFIX)/lib/python3/dist-packages \
	  $(RUN_PY) -c "import gir; gir.install_as_gi(); import runpy; runpy.run_path('$(SHOWTIME_PREFIX)/bin/showtime', run_name='__main__')"

# pyedit (examples/pyedit) — a gnome-text-editor-shaped showcase whose
# explicit purpose is to surface pygir-compat gaps. Exercises GTK4 +
# libadwaita + GtkSource-5 + Gtk.Template through the gir surface.
# Failures here are signal, not noise. `text-editor` is an alias matching
# the upstream binary name.
pyedit text-editor: build
	PYTHONPATH=$(abspath $(BDIR)/src):$(CURDIR) PYGIR_GI_TESTS_BUILDDIR=$(abspath $(BDIR)/packages/typelib) \
	  $(RUN_PY) -m examples.pyedit $(ARGS)

# web-browser (examples/web_browser) — an epiphany-shaped showcase that
# exercises WebKitGTK 6 alongside Gtk-4 / libadwaita. Same launcher
# pattern as pyedit. WebKit's GPU process spawns helpers, so this won't
# work under valgrind without extra suppressions.
web-browser: build
	PYTHONPATH=$(abspath $(BDIR)/src):$(CURDIR) \
	  $(RUN_PY) -m examples.web_browser $(ARGS)

# terminal (apps/terminal) — a gnome-terminal-shaped tabbed terminal
# that exercises Vte 3.91 alongside Gtk-4 / libadwaita. Each tab is a
# Vte.Terminal spawned into $SHELL; prefs (font, palette, scrollback,
# opacity, cursor) are JSON-persisted under $XDG_CONFIG_HOME.
terminal: build
	PYTHONPATH=$(abspath $(BDIR)/src):$(CURDIR) \
	  $(RUN_PY) -m apps.terminal $(ARGS)

# gnome-music (https://gitlab.gnome.org/GNOME/gnome-music) lives in apps/gnome-music.
# Real-app integration target — exercises GtkApplication, GStreamer, GTK4,
# libadwaita, GSettings, GResource, Grilo (media discovery), Tracker (sparql),
# libmediaart, libsoup. Meson installs into a local prefix so no system install
# is needed. The `gi.install_as_gi()` preamble routes the app's `from gi.repository`
# imports through pygir.
GNOME_MUSIC_DIR    := $(abspath apps/gnome-music)
GNOME_MUSIC_BDIR   := $(GNOME_MUSIC_DIR)/_build
GNOME_MUSIC_PREFIX := $(GNOME_MUSIC_DIR)/_install

gnome-music: build
	@mkdir -p $(GNOME_MUSIC_BDIR)
	@if [ -f $(GNOME_MUSIC_BDIR)/build.ninja ]; then \
		$(MESON) setup --reconfigure --prefix=$(GNOME_MUSIC_PREFIX) \
			-Dprofile=development \
			$(GNOME_MUSIC_BDIR) $(GNOME_MUSIC_DIR) > /dev/null; \
	else \
		$(MESON) setup --prefix=$(GNOME_MUSIC_PREFIX) \
			-Dprofile=development \
			$(GNOME_MUSIC_BDIR) $(GNOME_MUSIC_DIR) > /dev/null; \
	fi
	@$(NINJA) --quiet -C $(GNOME_MUSIC_BDIR) install
	@GSETTINGS_SCHEMA_DIR=$(GNOME_MUSIC_PREFIX)/share/glib-2.0/schemas \
	PYTHONPATH=$(abspath $(BDIR)/src):$(GNOME_MUSIC_PREFIX)/lib/python3/dist-packages \
	  $(RUN_PY) -c "import gir; gir.install_as_gi(); from gi.repository import GLib; import runpy; runpy.run_path('$(GNOME_MUSIC_PREFIX)/bin/gnome-music', run_name='__main__')"

# cambalache (https://gitlab.gnome.org/jpu/cambalache) lives in apps/cambalache.
# Real-app integration target — a GTK4 UI designer that exercises GtkApplication,
# libadwaita, GtkSourceView 5, custom GIRepository typelibs (CambalachePrivate +
# cmb_catalog_gen), GResource, GSettings, and the Casilda Wayland-compositor
# widget. Casilda is pulled in as a meson subproject; cambalache 1.2.4 wraps
# casilda 1.2.4 which needs wlroots-0.20, so the wrap+meson have been pinned
# to casilda 1.2.0 (wlroots-0.19 — available on Debian testing as
# libwlroots-0.19-dev). cmb_init_dev.py drives the meson build into a per-app
# .local prefix; we run it under system python3 because the build-time gi
# checks and `gi.Repository` paths in cmb_init_dev are not yet wired up
# through pygir. After install, we launch the venv interpreter with
# `gir.install_as_gi()` and the local prefix's typelibs/libs/schemas on the
# environment so pygir's shared repository inherits them at construction.
# cambalache's meson.build declares a pygobject-3.0 pkg-config dependency
# that is otherwise unused — a stub .pc is generated to satisfy the check
# without requiring `python-gi-dev`.
CAMBALACHE_DIR    := $(abspath apps/cambalache)
CAMBALACHE_LOCAL  := $(CAMBALACHE_DIR)/.local
CAMBALACHE_PKG    := $(CAMBALACHE_LOCAL)/pkgconfig-stub
CAMBALACHE_MA     := $(shell /usr/bin/python3 -c 'import sys; print(sys.implementation._multiarch)')

cambalache: build
	@if ! /usr/bin/pkg-config --exists wlroots-0.19; then \
	    echo "error: wlroots-0.19 not found via pkg-config."; \
	    echo "       Install with: sudo apt install libwlroots-0.19-dev"; \
	    exit 1; \
	fi
	@$(UV) pip install --quiet --python $(PY) lxml
	@mkdir -p $(CAMBALACHE_PKG)
	@printf 'Name: PyGObject\nDescription: pygir stub for cambalache build\nVersion: 3.56.2\nRequires: gobject-2.0\nCflags:\nLibs:\n' > $(CAMBALACHE_PKG)/pygobject-3.0.pc
	@cd $(CAMBALACHE_DIR) && PKG_CONFIG_PATH=$(CAMBALACHE_PKG):$$PKG_CONFIG_PATH \
	    /usr/bin/python3 -c "from tools.cmb_init_dev import cmb_init_dev; import sys; sys.exit(cmb_init_dev())"
	@GSETTINGS_SCHEMA_DIR=$(CAMBALACHE_LOCAL)/share/glib-2.0/schemas \
	XDG_DATA_DIRS=$(CAMBALACHE_LOCAL)/share:/usr/share:$$XDG_DATA_DIRS \
	GI_TYPELIB_PATH=$(CAMBALACHE_LOCAL)/lib/$(CAMBALACHE_MA)/girepository-1.0:$(CAMBALACHE_LOCAL)/lib/$(CAMBALACHE_MA)/cambalache:$(CAMBALACHE_LOCAL)/lib/$(CAMBALACHE_MA)/cmb_catalog_gen:$(CAMBALACHE_LOCAL)/lib/girepository-1.0$${GI_TYPELIB_PATH:+:$$GI_TYPELIB_PATH} \
	LD_LIBRARY_PATH=$(CAMBALACHE_LOCAL)/lib/$(CAMBALACHE_MA):$(CAMBALACHE_LOCAL)/lib/$(CAMBALACHE_MA)/cambalache:$(CAMBALACHE_LOCAL)/lib/$(CAMBALACHE_MA)/cmb_catalog_gen$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH} \
	PYTHONPATH=$(abspath $(BDIR)/src):$(CAMBALACHE_LOCAL)/lib/python3/dist-packages:$(CAMBALACHE_DIR):$(CAMBALACHE_DIR)/cambalache:$(CAMBALACHE_LOCAL)/bin$${PYTHONPATH:+:$$PYTHONPATH} \
	  $(RUN_PY) -c "import gir; gir.install_as_gi(); import sys; from cambalache.app import CmbApplication; sys.exit(CmbApplication().run(sys.argv))" $(ARGS)

DRAWING_DIR := $(abspath apps/drawing-run)
drawing: build
	@$(UV) pip install --quiet --python $(PY) pycairo
	@GSETTINGS_SCHEMA_DIR=$(DRAWING_DIR)/schemas \
	PYTHONPATH=$(abspath $(BDIR)/src) \
	  $(RUN_PY) $(DRAWING_DIR)/run.py

# Quod Libet (https://github.com/quodlibet/quodlibet) lives in apps/quod-libet.
# Real-app integration target — an old and well-maintained GTK3 music
# library/player. Exercises Gtk-3.0, Gdk-3.0, GdkPixbuf-2.0, Gst-1.0,
# Soup-3.0, Pango/PangoCairo, optional GdkX11, plus GObject signal-heavy
# Python code paths. No build step: the package is pure Python and is
# imported straight from the source tree. mutagen/feedparser/pycairo are
# pip-installed into the pygir venv to satisfy the app's runtime deps.
# The -c preamble pre-imports importlib.util/.machinery because QL's
# util/importhelper.py uses those attributes without importing them and
# CPython 3.14 no longer auto-loads them.
QUODLIBET_DIR := $(abspath apps/quod-libet)
quodlibet: build
	@$(UV) pip install --quiet --python $(PY) mutagen feedparser pycairo
	@PYTHONPATH=$(abspath $(BDIR)/src):$(QUODLIBET_DIR) \
	  $(RUN_PY) -c "import sys, importlib.util, importlib.machinery; sys.argv = ['quodlibet'] + sys.argv[1:]; import gir; gir.install_as_gi(); from quodlibet.main import main; sys.exit(main())" $(ARGS)

profile: build
	rm -f /tmp/perf-*.map /tmp/pygir.perf
	PYTHON_GIL=0 timeout 8 perf record -F 999 -g --call-graph fp \
	    -o /tmp/pygir.perf -- $(_ENV) $(RUN_PY) examples/mandelbrot/app.py || true
	@echo; echo "=== top symbols (>0.5% threshold) ==="
	perf report -i /tmp/pygir.perf --stdio --no-children -F overhead,symbol,dso \
	    -g none --percent-limit 0.5 2>/dev/null | grep -v "^#" | head -25

valgrind: build
	PYTHONMALLOC=malloc VALGRIND=1 $(_ENV) \
	    $(VALGRIND) $(VALGRIND_FLAGS) \
	    $(RUN_PYTEST) -s -n 0 $(if $(PYTEST_ARGS),$(PYTEST_ARGS),src/ginext/tests/)
	@echo; echo "=== valgrind summary (full log: $(VALGRIND_LOG)) ==="
	@grep -E "ERROR SUMMARY|definitely lost|indirectly lost" $(VALGRIND_LOG) | tail -5

test-sanitize:
	@$(MAKE) $(SANITIZER_TEST_TARGET) \
	    PYTHON=$(SANITIZER_PYTHON) \
	    PYTHON_ENV_NAME=$(SANITIZER_PYTHON)-$(SANITIZER_SUFFIX) \
	    BDIR=build/$(_SANITIZER_P)-$(SANITIZER_SUFFIX) \
	    MESON_SETUP_ARGS='$(MESON_SETUP_ARGS) $(_SANITIZE_MESON_ARG)' \
	    BUILD_ENV='ASAN_OPTIONS=$(ASAN_OPTIONS) UBSAN_OPTIONS=$(UBSAN_OPTIONS) $(_SANITIZER_BUILD_PRELOAD_ENV)' \
	    PYTEST_ENV='$(SANITIZER_ENV)' \
	    PYTEST_XDIST_ARGS='$(SANITIZER_PYTEST_XDIST_ARGS)' \
	    PYTEST_HANG_ARGS='$(SANITIZER_PYTEST_HANG_ARGS)' \
	    PYTEST_ARGS='$(SANITIZER_PYTEST_ARGS) $(PYTEST_ARGS)'

test-asan:
	@$(MAKE) test-sanitize SANITIZE=address SANITIZER_SUFFIX=asan SANITIZER_PYTEST_XDIST_ARGS='$(ASAN_PYTEST_XDIST_ARGS)'

test-ubsan:
	@$(MAKE) test-sanitize SANITIZE=undefined SANITIZER_SUFFIX=ubsan SANITIZER_PYTEST_XDIST_ARGS='$(UBSAN_PYTEST_XDIST_ARGS)'

%-debug:
	@$(MAKE) $* PYTHON=$(DEBUG_PYTHON) PYTEST_XDIST_ARGS= PYTEST_ARGS="$(DEBUG_PYTEST_ARGS) $(PYTEST_ARGS)"

# Run any target under gdb. Re-invokes `make $*` with the runtime
# python wrapped in `gdb --args ...`, so recipes that invoke either
# RUN_PY or RUN_PYTEST get debugged (test, run, drawing, showtime,
# profile, valgrind). The bare PY/PYTEST that the build/meson-setup
# phase needs stays unwrapped. gdb auto-runs the program and stays
# interactive on stop; pass `GDB_FLAGS=...` or `GDB_PYTEST_FLAGS=...`
# to override (e.g. for batch mode use `GDB_FLAGS='-batch -ex run -ex bt'`).
#
# `test-debug-gdb` is handled explicitly below so both
# `test-debug-gdb` and `test-gdb-debug` run the debug Python under gdb.
GDB              := /usr/bin/gdb
GDB_PYTEST_SCRIPT := $(abspath tools/gdb/pytest-xdist.gdb)
GDB_COMMON_FLAGS ?= -q -ex=set\ pagination\ off -ex=set\ print\ thread-events\ off -ex=set\ print\ inferior-events\ off -ex=set\ print\ frame-info\ short-location
GDB_ABORT_FLAGS  ?= -ex=handle\ SIGABRT\ stop\ print\ pass
GDB_FORK_FLAGS   ?= -ex=set\ follow-fork-mode\ parent -ex=set\ detach-on-fork\ on
GDB_ALL_FORKS_FLAGS ?= -ex=set\ follow-fork-mode\ parent -ex=set\ detach-on-fork\ off -ex=set\ schedule-multiple\ on
GDB_FLAGS        ?= $(GDB_COMMON_FLAGS) $(GDB_ABORT_FLAGS) -ex=run
GDB_PYTEST_FLAGS ?= $(GDB_COMMON_FLAGS) -x $(GDB_PYTEST_SCRIPT) $(GDB_ALL_FORKS_FLAGS) $(GDB_ABORT_FLAGS) -ex=goi-run-to-sigabrt
GDB_PYTEST_ARGS  ?=

%-debug-gdb:
	@$(MAKE) $*-gdb PYTHON=$(DEBUG_PYTHON)

%-gdb:
	@$(MAKE) $* \
	    RUN_PY='$(GDB) $(GDB_FLAGS) --args $(PY)' \
	    RUN_PYTEST='$(GDB) $(GDB_PYTEST_FLAGS) --args $(PY) $(PYTEST)' \
	    PYTEST_ARGS='$(PYTEST_ARGS) $(GDB_PYTEST_ARGS)'

%-coverage:
	@$(MAKE) $* \
	    BDIR=build/$(_P)-coverage \
	    MESON_SETUP_ARGS='$(MESON_SETUP_ARGS) -Db_coverage=true'

test-coverage:
	@$(MAKE) test \
	    BDIR=build/$(_P)-coverage \
	    MESON_SETUP_ARGS='$(MESON_SETUP_ARGS) -Db_coverage=true'
	@$(MAKE) coverage-report \
	    BDIR=build/$(_P)-coverage \
	    MESON_SETUP_ARGS='$(MESON_SETUP_ARGS) -Db_coverage=true'

coverage-report:
	@echo; echo "=== coverage summary ($(BDIR)) ==="
	@$(GCOVR) $(GCOVR_ARGS)

clean:
	@rm -rf build .venv*
