from __future__ import annotations

import importlib
import os
import pathlib
import sys

import pytest

from conftest_shared import (
    configure_subprocess_marker,
    maybe_run_test_in_subprocess,
    setup_gi_test_env,
)

# Shared private-session-D-Bus fixture (repo root is on sys.path via the
# `pythonpath` pytest setting); available to pygobject D-Bus tests.
from dbus_fixtures import dbus_session_bus as dbus_session_bus

# The introspection test typelibs (Regress, GIMarshallingTests, ...) must be on
# GI_TYPELIB_PATH before ginext is first imported — the repository's search path
# is fixed at import time. The detection lives once in conftest_shared; this
# package's tests use this directory as the pytest rootdir, so the repo-root
# conftest is not loaded and this effective-root conftest does the setup.
setup_gi_test_env(pathlib.Path(__file__).resolve().parents[3])

_ginext = importlib.import_module("ginext")


_src_ginext = pathlib.Path(__file__).resolve().parents[3] / "src" / "ginext"
if _src_ginext.is_dir() and str(_src_ginext) not in _ginext.__path__:
    _ginext.__path__.insert(0, str(_src_ginext))

del _ginext, _src_ginext

# GTK test files require a real display.  Without one, GTK4 crashes at type
# initialisation rather than returning False from gtk_init_check().  Skip
# them entirely at collection time so they never get imported.
_pygobject_dir = pathlib.Path(__file__).parent / "pygobject"
_HAS_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
_GIL_DISABLED = hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled()
collect_ignore = (
    []
    if _HAS_DISPLAY
    else [
        str(_pygobject_dir / "test_overrides_gtk.py"),
        str(_pygobject_dir / "test_gtk_template.py"),
    ]
)
del _pygobject_dir, _HAS_DISPLAY, _GIL_DISABLED, os, pathlib, sys


def pytest_configure(config: pytest.Config) -> None:
    configure_subprocess_marker(config)


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    return maybe_run_test_in_subprocess(pyfuncitem)


@pytest.fixture(scope="session")
def wayland() -> dict[object, object]:
    return {}
