# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


_SUBPROCESS_MARK = "subprocess"
_SUBPROCESS_ENV = "PYGIR_PYTEST_SUBPROCESS"


def _restore_asan_preload() -> None:
    asan_runtime = os.environ.get("PYGIR_ASAN_RUNTIME")
    if not asan_runtime or sys.platform != "darwin":
        return
    assert isinstance(asan_runtime, str)
    existing = os.environ.get("DYLD_INSERT_LIBRARIES", "")
    if asan_runtime not in existing.split(":"):
        os.environ["DYLD_INSERT_LIBRARIES"] = (
            f"{asan_runtime}:{existing}" if existing else asan_runtime
        )


_restore_asan_preload()


def suppress_editable_rebuild() -> tuple[list[str] | None, str | None]:
    build_path = None
    ninja_cmd = None
    for finder in sys.meta_path:
        if type(finder).__name__ != "MesonpyMetaFinder":
            continue
        finder_vars = vars(finder)
        modules = finder_vars.get("_top_level_modules") or ()
        if "ginext" not in modules:
            continue
        build_path = finder_vars.get("_build_path")
        ninja_cmd = finder_vars.get("_build_cmd")
        break
    if build_path is None:
        return None, None

    plan_path = Path(build_path) / "meson-info" / "intro-install_plan.json"
    if plan_path.exists():
        ext_suffixes = set(importlib.machinery.EXTENSION_SUFFIXES)
        data = json.loads(plan_path.read_text())
        for section in data.values():
            for src, info in section.items():
                dest = info.get("destination", "")
                if dest.startswith("{py_platlib}") and any(
                    src.endswith(suffix) for suffix in ext_suffixes
                ):
                    so_dir = str(Path(src).parent)
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


def rebuild_editable(
    ninja_cmd: list[str] | None,
    build_path: str | None,
) -> None:
    del ninja_cmd, build_path
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return
    saved = os.environ.pop("PYTHON_GIL", None)
    try:
        for finder in sys.meta_path:
            if type(finder).__name__ != "MesonpyMetaFinder":
                continue
            finder_vars = vars(finder)
            cmd = finder_vars.get("_build_cmd")
            path = finder_vars.get("_build_path")
            if not cmd or not path:
                continue
            try:
                subprocess.run(cmd, cwd=path, stdout=subprocess.DEVNULL, check=True)
            except OSError | subprocess.SubprocessError:
                pass
    finally:
        if saved is not None:
            os.environ["PYTHON_GIL"] = saved


def setup_package_paths(root: Path) -> None:
    overlay_dirs: list[str] = []
    for path in sorted((root / "packages").glob("*/src"), reverse=True):
        path_s = str(path)
        if path_s not in sys.path:
            sys.path.insert(0, path_s)
        overlay_dirs.extend(
            str(overlay_path)
            for overlay_path in sorted(path.glob("*_*/_overlays"))
            if overlay_path.is_dir()
        )
    if overlay_dirs:
        existing = os.environ.get("GINEXT_OVERLAY_PATH", "")
        parts = [part for part in existing.split(os.pathsep) if part]
        for overlay_dir in reversed(overlay_dirs):
            if overlay_dir in parts:
                continue
            parts.insert(0, overlay_dir)
        os.environ["GINEXT_OVERLAY_PATH"] = os.pathsep.join(parts)


def register_win_dll_dirs() -> None:
    if sys.platform != "win32":
        return
    for dll_dir in os.environ.get("GINEXT_WIN_DLL_DIRS", "").split(os.pathsep):
        if dll_dir and os.path.isdir(dll_dir) and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_dir)


def setup_split_package_test_env(
    root: Path,
    *,
    include_ginext_tests: bool = False,
) -> None:
    register_win_dll_dirs()
    setup_package_paths(root)
    if not include_ginext_tests:
        return
    import ginext

    src_ginext = root / "src" / "ginext"
    src_ginext_s = str(src_ginext)
    if src_ginext.is_dir() and src_ginext_s not in ginext.__path__:
        ginext.__path__.insert(0, src_ginext_s)


def setup_gtk_version_from_mark(default: str = "4.0") -> None:
    version = "3.0" if _mark_expression() == "not gtk4" else default

    from ginext import defaults

    defaults.require("Gtk", version)
    for namespace, implied_version in (
        defaults.implied_defaults_map().get(("Gtk", version), {}).items()
    ):
        defaults.require(namespace, implied_version)


def _mark_expression() -> str | None:
    for index, arg in enumerate(sys.argv):
        if arg in {"-m", "--markexpr"}:
            if index + 1 < len(sys.argv):
                return sys.argv[index + 1].strip()
            return None
        if arg.startswith("--markexpr="):
            return arg.partition("=")[2].strip()
    return None


def setup_gi_test_env(root: Path, build_path: str | None = None) -> None:
    register_win_dll_dirs()
    candidates: list[Path] = []
    for envvar in ("PYGIR_GI_TESTS_BUILDDIR", "GINEXT_GI_TESTS_BUILDDIR"):
        explicit = os.environ.get(envvar)
        if explicit:
            candidates.append(Path(explicit))
    for entry in sys.path:
        if not entry:
            continue
        resolved = Path(entry).resolve()
        if "build" not in resolved.parts:
            continue
        candidates.append(resolved / "packages" / "typelib")
        candidates.append(resolved.parent / "packages" / "typelib")
        break
    if build_path:
        candidates.append(Path(build_path) / "packages" / "typelib")
    candidates.append(root / "build" / "packages" / "typelib")
    candidates.extend(sorted((root / "build").glob("*/packages/typelib")))

    builddir = next(
        (c for c in candidates if (c / "Regress-1.0.typelib").exists()), None
    )
    if builddir is None:
        return
    builddir_s = str(builddir)
    os.environ.setdefault("PYGIR_GI_TESTS_BUILDDIR", builddir_s)
    os.environ.setdefault("GINEXT_GI_TESTS_BUILDDIR", builddir_s)
    for var in ("GI_TYPELIB_PATH", "LD_LIBRARY_PATH"):
        existing = os.environ.get(var, "")
        if builddir_s not in existing.split(os.pathsep):
            os.environ[var] = (
                f"{builddir_s}{os.pathsep}{existing}" if existing else builddir_s
            )
    preload_gi_test_libraries(builddir)


def preload_gi_test_libraries(builddir: Path) -> None:
    from ginext.private import preload_shared_library

    if sys.platform == "win32":
        suffix, prefix = ".dll", ""
    elif sys.platform == "darwin":
        suffix, prefix = ".dylib", "lib"
    else:
        suffix, prefix = ".so", "lib"

    for base in ("utility", "regress", "gimarshallingtests", "goibench"):
        path = builddir / f"{prefix}{base}{suffix}"
        if path.exists():
            preload_shared_library(str(path))


def configure_subprocess_marker(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "subprocess(timeout=30): rerun the test body in a fresh pytest subprocess",
    )


def maybe_run_test_in_subprocess(pyfuncitem: pytest.Function) -> bool | None:
    if os.environ.get(_SUBPROCESS_ENV):
        return None

    marker = pyfuncitem.get_closest_marker(_SUBPROCESS_MARK)
    if marker is None:
        return None

    timeout = marker.kwargs.get("timeout", 30)
    if marker.args:
        pytest.fail("pytest.mark.subprocess accepts keyword arguments only")
    if not isinstance(timeout, int | float):
        pytest.fail("pytest.mark.subprocess(timeout=...) requires a number")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        pyfuncitem.nodeid,
        "--rootdir",
        str(pyfuncitem.config.rootpath),
        "-n",
        "0",
        "-q",
    ]
    if pyfuncitem.config.option.runxfail:
        cmd.append("--runxfail")

    env = os.environ.copy()
    env[_SUBPROCESS_ENV] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(pyfuncitem.config.rootpath),
        env=env,
        capture_output=True,
        text=True,
        timeout=float(timeout),
        check=False,
    )
    if proc.returncode != 0:
        details = []
        if proc.stdout:
            details.append(f"stdout:\n{proc.stdout}")
        if proc.stderr:
            details.append(f"stderr:\n{proc.stderr}")
        rendered = "\n\n".join(details) if details else "no subprocess output"
        pytest.fail(
            f"{pyfuncitem.nodeid} failed in subprocess (exit {proc.returncode})\n\n{rendered}"
        )
    return True
