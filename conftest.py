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

from __future__ import annotations

import importlib.machinery
import importlib
from typing import cast, Any
import json
import os
import pathlib
import subprocess
import sys

import pytest

# Windows: register the DLL search dirs (GINEXT_WIN_DLL_DIRS) before anything
# imports the _gobject extension below — a .pyd's dependent DLLs aren't found via
# PATH, only via os.add_dll_directory. Runs here (the root conftest, loaded
# first) so it also covers spawned pytest subprocesses. See tools/win/run_tests.py.
if sys.platform == "win32":
    for _dll_dir in os.environ.get("GINEXT_WIN_DLL_DIRS", "").split(os.pathsep):
        if _dll_dir and os.path.isdir(_dll_dir):
            os.add_dll_directory(_dll_dir)

from conftest_shared import (
    configure_subprocess_marker,
    maybe_run_test_in_subprocess,
    setup_gi_test_env,
)


def _suppress_editable_rebuild() -> tuple[list[str] | None, str | None]:
    # Under an editable (meson-python) install the import hook tries to rebuild
    # the wheel by invoking `meson`, which is not on PATH at test time and fails
    # (see _ginext_editable_loader.MARKER == "MESONPY_EDITABLE_SKIP"). Tell the
    # loader to skip its rebuild, point the path at the already-built extension,
    # and rebuild once via ninja directly in _rebuild_editable(). This is a
    # no-op when running against PYTHONPATH=build/<py>/src (no editable finder).
    build_path = None
    ninja_cmd = None
    for finder in sys.meta_path:
        if type(finder).__name__ != "MesonpyMetaFinder":
            continue
        # Only the core ginext finder is suppressed and rebuilt here. Compiled
        # overlay-package finders (e.g. ginext_gst) are left active so they keep
        # serving their own extension module; their recorded ninja is valid (they
        # are installed --no-build-isolation), so their import-time rebuild is a
        # cheap no-op rather than a crash.
        modules = getattr(finder, "_top_level_modules", None) or ()
        if "ginext" not in modules:
            continue
        build_path = getattr(finder, "_build_path", None)
        ninja_cmd = getattr(finder, "_build_cmd", None)
        break
    if build_path is None:
        return None, None

    plan_path = pathlib.Path(build_path) / "meson-info" / "intro-install_plan.json"
    if plan_path.exists():
        ext_suffixes = set(importlib.machinery.EXTENSION_SUFFIXES)
        data = json.loads(plan_path.read_text())
        for section in data.values():
            for src, info in section.items():
                dest = info.get("destination", "")
                if dest.startswith("{py_platlib}") and any(
                    src.endswith(suffix) for suffix in ext_suffixes
                ):
                    so_dir = str(pathlib.Path(src).parent)
                    if so_dir not in sys.path:
                        sys.path.insert(0, so_dir)
                    existing = os.environ.get("PYTHONPATH", "")
                    if so_dir not in existing.split(os.pathsep):
                        os.environ["PYTHONPATH"] = (
                            f"{so_dir}{os.pathsep}{existing}" if existing else so_dir
                        )
                    break

    existing = os.environ.get("MESONPY_EDITABLE_SKIP", "")
    if build_path not in existing.split(os.pathsep):
        os.environ["MESONPY_EDITABLE_SKIP"] = (
            f"{existing}{os.pathsep}{build_path}" if existing else build_path
        )
    return ninja_cmd, build_path


_NINJA_CMD, _BUILD_PATH = _suppress_editable_rebuild()


def _rebuild_editable() -> None:
    # Build the editable extension once, here at import time, before `ginext` is
    # imported below. mesonpy's import-time rebuild is suppressed above, so this
    # is the only rebuild. Under xdist the controller builds here before workers
    # spawn; workers skip and inherit the fresh build.
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    saved = os.environ.pop("PYTHON_GIL", None)
    try:
        # Rebuild every meson-python editable once here. The core finder is
        # suppressed (workers use its .so dir on sys.path), but compiled
        # overlay-package finders (ginext_gst) stay active and rebuild on import,
        # so their build must be current *before* workers spawn — otherwise the
        # workers race on a concurrent ninja in the same build dir.
        for finder in sys.meta_path:
            if type(finder).__name__ != "MesonpyMetaFinder":
                continue
            finder_vars = vars(finder)
            ninja_cmd = finder_vars.get("_build_cmd")
            build_path = finder_vars.get("_build_path")
            if not ninja_cmd or not build_path:
                continue
            try:
                subprocess.run(
                    ninja_cmd, cwd=build_path, stdout=subprocess.DEVNULL, check=True
                )
            except (OSError, subprocess.SubprocessError):
                pass
    finally:
        if saved is not None:
            os.environ["PYTHON_GIL"] = saved
    _precompile_editable_bytecode()


def _precompile_editable_bytecode() -> None:
    # The meson-python editable loader disables bytecode caching (its set_data is
    # a no-op), so every process re-compiles the editable library modules from
    # source on import — ~80 ms for ginext core alone, paid by the controller,
    # every xdist worker, and every subprocess child. The inherited
    # SourceFileLoader.get_code still *reads* a fresh .pyc, so compile the editable
    # source trees once here (controller only, before workers spawn) and they all
    # read the cache instead. compileall is a near-no-op when the cache is already
    # current (it skips files whose .pyc matches the source mtime).
    import compileall
    import re

    root = pathlib.Path(__file__).resolve().parent
    targets = [root / "src" / "ginext", *sorted((root / "packages").glob("*/src"))]
    # Only the editable *library* modules are loaded through the meson finder that
    # skips bytecode caching; test modules are imported by pytest's own (caching)
    # importer, so skip the tests/ trees to keep this near-instant.
    skip_tests = re.compile(r"[\\/]tests[\\/]")
    for target in targets:
        if not target.is_dir():
            continue
        try:
            compileall.compile_dir(str(target), quiet=1, force=False, rx=skip_tests)
        except OSError:
            # Bytecode precompilation is a pure optimization; never let it break
            # the test session (e.g. a read-only or racing __pycache__).
            pass


_rebuild_editable()


# Make the gobject-introspection test typelibs available before ginext is
# imported below (the repository's search path is fixed at first import). The
# detection lives once in conftest_shared.setup_gi_test_env; every effective-root
# conftest calls it.
setup_gi_test_env(pathlib.Path(__file__).resolve().parent, _BUILD_PATH)


# The `gi` package is the PyGObject compatibility layer and raises ImportError
# unless the `pygobject_compat` feature is enabled. Its test suite lives under
# src/gi/tests, and pytest imports those modules as `gi.tests.*` — which imports
# `gi` first. That happens while pytest loads the per-directory conftests at
# startup (before any collection hook runs), so the feature must be enabled here
# at root-conftest import time, the earliest point pytest gives us. Native
# ginext tests reset feature flags during teardown, so src/gi/tests/conftest.py
# re-asserts this per test; here it only needs to cover collection-time imports.
ginext = importlib.import_module("ginext")

ginext.features.set_enabled("pygobject_compat", True)


_WAYLAND_PLUGIN = "ginext.tests.wayland_fixture"
_WAYLAND_PATH = (
    pathlib.Path(__file__).resolve().parent
    / "src"
    / "ginext"
    / "tests"
    / "wayland_fixture.py"
)


def pytest_configure(config: object) -> None:
    # The Gtk tests in both src/gi/tests and src/ginext/tests use the `wayland`
    # display fixture from ginext.tests.wayland_fixture. The ginext test tree
    # registers it via its own conftest's pytest_plugins; when only src/gi/tests
    # is collected that conftest is not loaded, so register the plugin here as a
    # fallback. Loading by path (rather than importing ginext.tests, which is
    # not shipped in the build/installed package) keeps it working under both
    # `make test` and `uv run pytest`. Registering under the same plugin name
    # makes pytest deduplicate against the ginext conftest's registration.
    import importlib.util

    pm = cast("Any", config).pluginmanager
    configure_subprocess_marker(cast("pytest.Config", config))
    if pm.has_plugin(_WAYLAND_PLUGIN):
        return
    spec = importlib.util.spec_from_file_location(_WAYLAND_PLUGIN, _WAYLAND_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    pm.register(module, _WAYLAND_PLUGIN)


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    return maybe_run_test_in_subprocess(pyfuncitem)


@pytest.fixture(autouse=True)
def _isolate_feature_overrides() -> object:
    # Feature flags are process-global. Tests toggle them via features.set_enabled
    # and often "restore" with set_enabled(name, False), which writes an explicit
    # override that outranks implied defaults (e.g. pygobject_compat implies
    # old_signal_api=True) — so a leaked override silently breaks unrelated tests
    # sharing the xdist worker. Snapshot and restore the override map around every
    # test so no toggle can escape its own test.
    ginext_mod = importlib.import_module("ginext")
    features = ginext_mod.features
    saved = features.overrides_snapshot()
    try:
        yield
    finally:
        features.overrides_restore(saved)
