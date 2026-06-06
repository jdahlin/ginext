#!/usr/bin/env python3
"""Run the ginext test suite on Windows.

A Python runner (vs a shell script) so the Windows-specific runtime wiring lives
in the language the project is written in. It runs pytest in-process after
registering the DLL search directories, so the built _gobject extension and the
typelibs' shared libraries resolve without a global PATH hack.

Machine-specific locations default to this checkout's dev layout and can be
overridden via environment:
  GINEXT_VCPKG_BIN   dir holding glib/gobject/gio/girepository/cairo DLLs
  GINEXT_CORE_TYPELIBS dir holding the core .typelib files (GLib, GObject, Gio, GIRepository-3.0, ...)

Usage:  python tools/win/run_tests.py src/ginext/tests/gobject -q
        (any trailing args are passed through to pytest)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Triplet-aware so the same runner works for arm64-windows and x64-windows.
_TRIPLET = os.environ.get("GINEXT_TRIPLET", "arm64-windows")
_ARCH = _TRIPLET.replace("-windows", "")
BUILD = ROOT / "build" / f"win-{_ARCH}"
TEST_TYPELIBS = BUILD / "packages" / "typelib"

# vcpkg install tree: prefer the one build-env.ps1 resolved (manifest mode's
# vcpkg_installed vs classic), exported as GINEXT_VCPKG_INSTALLED.
_INSTALLED = os.environ.get("GINEXT_VCPKG_INSTALLED") or rf"C:\dev\vcpkg\installed\{_TRIPLET}"
VCPKG_BIN = Path(os.environ.get("GINEXT_VCPKG_BIN", str(Path(_INSTALLED) / "bin")))
CORE_TYPELIBS = Path(
    os.environ.get("GINEXT_CORE_TYPELIBS", str(Path(_INSTALLED) / "lib" / "girepository-1.0"))
)


def main(argv: list[str]) -> int:
    if sys.platform == "win32":
        dll_dirs = [str(d) for d in (VCPKG_BIN, TEST_TYPELIBS) if d.is_dir()]
        for d in dll_dirs:
            os.add_dll_directory(d)
        # Exported so spawned pytest subprocesses (subprocess marker, xdist
        # workers) register the same dirs via the tests' conftest.
        os.environ["GINEXT_WIN_DLL_DIRS"] = os.pathsep.join(dll_dirs)

    os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(
        str(p) for p in (TEST_TYPELIBS, CORE_TYPELIBS) if p.is_dir()
    )
    os.environ.setdefault("PYGIR_GI_TESTS_BUILDDIR", str(TEST_TYPELIBS))
    os.environ.setdefault("GOI_BENCH_BUILDDIR", str(TEST_TYPELIBS))

    path_dirs = [
        str(p)
        for p in (
            BUILD / "src",
            ROOT / "packages" / "ginext-gio" / "src",
            ROOT / "packages" / "ginext-gtk" / "src",
            ROOT / "packages" / "ginext-gst" / "src",
            ROOT / "packages" / "ginext-libsoup" / "src",
            ROOT / "packages" / "ginext-gi-compat" / "src",
            ROOT,
        )
        if p.is_dir()
    ]
    for sub in path_dirs:
        sys.path.insert(0, sub)
    # Exported so spawned pytest subprocesses (subprocess marker, xdist workers)
    # import ginext + the packages from the same locations.
    existing = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = os.pathsep.join(
        path_dirs + ([existing] if existing else [])
    )

    import pytest

    return pytest.main(["-p", "no:cacheprovider", "--no-header", *argv])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
