from __future__ import annotations

import itertools
import os
import pathlib

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

from conftest_shared import (
    configure_subprocess_marker,
    maybe_run_test_in_subprocess,
    setup_split_package_test_env,
)

setup_split_package_test_env(_REPO_ROOT, include_ginext_tests=True)

import ginext as _ginext
import pytest
from ginext import defaults as _defaults
from ginext_gtk import _defaults as _gtk_defaults

_ginext.features.set_enabled("pygobject_compat", True)
_defaults._implied_defaults_map_cache = dict(_gtk_defaults.IMPLIED_DEFAULTS)

del _defaults, _ginext

_WAYLAND_PLUGIN = "ginext.tests.wayland_fixture"
_WAYLAND_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "src"
    / "ginext"
    / "tests"
    / "wayland_fixture.py"
)


def pytest_configure(config: object) -> None:
    import importlib.util
    from typing import Any, cast

    configure_subprocess_marker(cast("pytest.Config", config))
    pm = cast("Any", config).pluginmanager
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


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    del config
    gtk4_dirs = {"gtk4", "gdk", "pango"}
    gtk4_mark = pytest.mark.gtk4

    for item in items:
        rel_parts = _relative_test_parts(item)
        if rel_parts is None:
            continue
        if rel_parts[0] in gtk4_dirs:
            item.add_marker(gtk4_mark)


def _gtk3_is_active() -> bool:
    # True when the current process is pinned to Gtk 3: either the dedicated
    # gtk3 subprocess spawned by test_gtk3_subprocess.py, or `make test`'s gtk3
    # phase (GINEXT_VERSIONS=Gtk:3.0). Everywhere else the process is Gtk 4.
    if os.environ.get("PYGIR_GTK3_SUBPROCESS"):
        return True
    return "Gtk:3" in os.environ.get("GINEXT_VERSIONS", "")


def pytest_ignore_collect(collection_path: pathlib.Path, config: pytest.Config) -> bool:
    del config
    try:
        rel = collection_path.resolve().relative_to(
            pathlib.Path(__file__).resolve().parent
        )
    except ValueError:
        return False
    parts = tuple(rel.parts)
    if not parts:
        return False
    if parts[0] == "gsk":
        return True
    # Gtk 3 and Gtk 4 are process-global singletons that cannot coexist. In a
    # normal (Gtk-4) run, skip importing the gtk3 tree entirely — importing some
    # of those modules disables GTK auto-init for the whole worker and segfaults
    # later gtk4 widget tests. The gtk3 suite is instead executed in a dedicated
    # Gtk:3.0 subprocess by test_gtk3_subprocess.py. When the process is itself
    # pinned to Gtk 3 (that subprocess, or `make test`'s gtk3 phase), collect it.
    return parts[0] == "gtk3" and not _gtk3_is_active()


def _relative_test_parts(item: pytest.Item) -> tuple[str, ...] | None:
    path = getattr(item, "path", None)
    if path is None:
        return None
    try:
        rel = (
            pathlib.Path(path)
            .resolve()
            .relative_to(pathlib.Path(__file__).resolve().parent)
        )
    except ValueError:
        return None
    parts = tuple(rel.parts)
    if not parts:
        return None
    return parts


_type_name_counter = itertools.count()


@pytest.fixture
def unique_type_name():
    def _next(prefix: str = "GinextPropTest") -> str:
        return f"{prefix}{next(_type_name_counter):04d}"

    return _next
