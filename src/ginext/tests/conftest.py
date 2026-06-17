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

import atexit
import importlib.machinery
import itertools
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
import types
from typing import TYPE_CHECKING, Protocol, cast

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from ginext.gobject.gtype import GType as GTypeClass
    from ginext.GObject import Object as _GObjectBase


class _MakeSubclass(Protocol):
    def __call__(
        self,
        fields: dict[str, tuple[type, object]] | None = ...,
        *,
        base: type | None = ...,
        prefix: str = ...,
        attrs: dict[str, object] | None = ...,
    ) -> type: ...


class _MakePropertyClass(Protocol):
    def __call__(
        self,
        annotation: type,
        *,
        name: str = ...,
        prefix: str = ...,
        base: type | None = ...,
        **property_kwargs: object,
    ) -> type: ...


class _PropertyFactory(Protocol):
    def __call__(self, **kwargs: object) -> object: ...


pytest_plugins = ["ginext.tests.wayland_fixture"]


ROOT = pathlib.Path(__file__).resolve().parents[3]
_GINEXT_ENV_VARS = ("GINEXT_APP", "GINEXT_VERSIONS", "GINEXT_FEATURES")


@pytest.fixture(autouse=True)
def _reset_ginext_features() -> Generator[None]:
    import ginext

    ginext.features.reset_for_test()
    try:
        yield
    finally:
        ginext.features.reset_for_test()


# Use the local (non-D-Bus) GIO backends for the whole test session, so file
# operations never spin up the gvfs/volume-monitor backends (which would open a
# session-bus connection of their own). GLib's own gdbus tests do the same.
os.environ.setdefault("GIO_USE_VFS", "local")
os.environ.setdefault("GIO_USE_VOLUME_MONITOR", "unix")


# Run the whole test session against a private dbus-daemon on /tmp, isolated from
# the developer's real session bus. Without this, code that touches the session
# bus (e.g. the gi.repository gdbus test module probes it at *import* time, and
# GDK probes the settings portal at display init) reaches into the real bus —
# caching connections for the process lifetime and coupling tests to the host.
# The daemon must be started here, at conftest import, because the address has to
# be set in the environment before pytest collects (imports) the test modules —
# too early for a fixture. Each process (and xdist worker) gets its own bus via a
# pid-unique socket; it is torn down at interpreter exit.
#
# The bus runs from a hand-written config with *no* <servicedir>: it is a pure
# message bus that never auto-activates services. That matters because GDK's
# Wayland display init makes a synchronous, 25s-timeout call to
# org.freedesktop.portal.Desktop; on a bus that can auto-activate the portal but
# can't bring it up headless, that call blocks the full timeout. With no service
# dirs the call fails instantly (NameHasNoOwner) and GDK falls back cleanly.
_PRIVATE_DBUS_DAEMON: subprocess.Popen[bytes] | None = None

_DBUS_CONFIG_TEMPLATE = """\
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>{address}</listen>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def _start_private_session_bus() -> None:
    global _PRIVATE_DBUS_DAEMON

    if os.environ.get("GINEXT_NO_PRIVATE_DBUS"):
        return

    dbus_daemon = shutil.which("dbus-daemon")
    if dbus_daemon is None:
        return  # dbus tests skip themselves when no session bus is available

    runtime_dir = tempfile.mkdtemp(prefix="ginext-dbus-")
    socket_path = os.path.join(runtime_dir, f"bus-{os.getpid()}-{uuid.uuid4().hex[:8]}")
    config_path = pathlib.Path(runtime_dir, "session.conf")
    address = f"unix:path={socket_path}"
    with config_path.open("w") as fh:
        fh.write(_DBUS_CONFIG_TEMPLATE.format(address=address))

    proc = subprocess.Popen(
        [dbus_daemon, f"--config-file={config_path}", "--nofork", "--print-address"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    # --print-address writes one line once the bus is listening: a readiness gate.
    ready = proc.stdout.readline().decode().strip() if proc.stdout else ""
    if not ready or proc.poll() is not None:
        proc.kill()
        shutil.rmtree(runtime_dir, ignore_errors=True)
        return

    os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
    for var in ("DBUS_STARTER_ADDRESS", "DBUS_STARTER_BUS_TYPE"):
        os.environ.pop(var, None)
    _PRIVATE_DBUS_DAEMON = proc
    atexit.register(_stop_private_session_bus, proc, runtime_dir)


def _stop_private_session_bus(proc: subprocess.Popen[bytes], runtime_dir: str) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    shutil.rmtree(runtime_dir, ignore_errors=True)


_start_private_session_bus()


def _suppress_editable_rebuild() -> tuple[list[str] | None, str | None]:
    build_path = None
    ninja_cmd = None

    for finder in sys.meta_path:
        if type(finder).__name__ != "MesonpyMetaFinder":
            continue
        finder_obj: object = finder
        # Only the core ginext finder is suppressed here; compiled overlay-package
        # finders (e.g. ginext_gst) stay active so they keep serving their own
        # extension module.
        modules = getattr(finder_obj, "_top_level_modules", None) or ()
        if "ginext" not in modules:
            continue
        build_path = finder_obj._build_path
        ninja_cmd = finder_obj._build_cmd
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


def _find_gi_tests_builddir() -> pathlib.Path | None:
    explicit = os.environ.get("GINEXT_GI_TESTS_BUILDDIR")
    if explicit:
        path = pathlib.Path(explicit)
        return path if path.is_dir() else None

    candidates = [
        ROOT / "build" / "packages" / "typelib",
    ]
    candidates.extend(
        path / "packages" / "typelib"
        for path in sorted((ROOT / "build").glob("*"))
        if path.is_dir()
    )
    for candidate in candidates:
        if (candidate / "Regress-1.0.typelib").exists():
            return candidate
    return None


GI_TESTS_BUILDDIR = _find_gi_tests_builddir()

if GI_TESTS_BUILDDIR is not None:
    builddir = str(GI_TESTS_BUILDDIR)
    existing = os.environ.get("GI_TYPELIB_PATH", "")
    os.environ["GI_TYPELIB_PATH"] = (
        f"{builddir}{os.pathsep}{existing}" if existing else builddir
    )


_CTYPES_PRELOADED = "ctypes" in sys.modules


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | object) -> None:
    if not _CTYPES_PRELOADED and "ctypes" in sys.modules:
        raise RuntimeError(
            "ctypes was imported during the test session — "
            "all GLib type registration must go through the C extension, not ctypes"
        )


def pytest_sessionstart(session: pytest.Session) -> None:
    if os.environ.get("PYTEST_XDIST_WORKER"):
        return

    saved = os.environ.pop("PYTHON_GIL", None)
    try:
        # Rebuild every meson-python editable once (controller only). The core
        # finder is suppressed, but compiled overlay finders (ginext_gst) stay
        # active and rebuild on import, so their build must be current before
        # workers spawn or they race on a concurrent ninja in one build dir.
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
            except OSError, subprocess.SubprocessError:
                pass
    finally:
        if saved is not None:
            os.environ["PYTHON_GIL"] = saved


GTYPE_CONSTANTS = [
    pytest.param("BOOLEAN", "gboolean", id="gboolean"),
    pytest.param("CHAR", "gchar", id="gchar"),
    pytest.param("UCHAR", "guchar", id="guchar"),
    pytest.param("INT", "gint", id="gint"),
    pytest.param("UINT", "guint", id="guint"),
    pytest.param("LONG", "glong", id="glong"),
    pytest.param("ULONG", "gulong", id="gulong"),
    pytest.param("INT64", "gint64", id="gint64"),
    pytest.param("UINT64", "guint64", id="guint64"),
    pytest.param("FLOAT", "gfloat", id="gfloat"),
    pytest.param("DOUBLE", "gdouble", id="gdouble"),
    pytest.param("STRING", "gchararray", id="gchararray"),
    pytest.param("GTYPE", "GType", id="GType"),
    pytest.param("PARAM", "GParam", id="GParam"),
    pytest.param("OBJECT", "GObject", id="GObject"),
    pytest.param("BOXED", "GBoxed", id="GBoxed"),
    pytest.param("POINTER", "gpointer", id="gpointer"),
]

PSPEC_GTYPE_CONSTANTS = [
    param for param in GTYPE_CONSTANTS if param.values[0] != "BOXED"
]


GINT_MIN = -(2**31)
GINT_MAX = 2**31 - 1
GINT64_MIN = -(2**63)
GINT64_MAX = 2**63 - 1

PARAM_READABLE = 1 << 0
PARAM_WRITABLE = 1 << 1
PARAM_READWRITE = PARAM_READABLE | PARAM_WRITABLE
PARAM_CONSTRUCT = 1 << 2
PARAM_CONSTRUCT_ONLY = 1 << 3
PARAM_USER_MASK = (
    PARAM_READABLE | PARAM_WRITABLE | PARAM_CONSTRUCT | PARAM_CONSTRUCT_ONLY
)


@dataclass(frozen=True)
class ValueTypeCase:
    annotation: type
    gtype_name: str
    zero: object
    sample: object


BUILTIN_VALUE_TYPES = [
    pytest.param(ValueTypeCase(bool, "gboolean", False, True), id="bool"),
    pytest.param(ValueTypeCase(int, "gint64", 0, 42), id="int"),
    pytest.param(ValueTypeCase(float, "gdouble", 0.0, 3.14), id="float"),
    pytest.param(ValueTypeCase(str, "gchararray", None, "hello"), id="str"),
]


@dataclass(frozen=True)
class NumericBoundsCase:
    constant: str
    minimum: int | float
    maximum: int | float
    default: int | float


NUMERIC_BOUNDS_TYPES = [
    pytest.param(NumericBoundsCase("CHAR", -5, 5, 3), id="gchar"),
    pytest.param(NumericBoundsCase("UCHAR", 1, 10, 7), id="guchar"),
    pytest.param(NumericBoundsCase("INT", 0, 100, 50), id="gint"),
    pytest.param(NumericBoundsCase("UINT", 1, 100, 50), id="guint"),
    pytest.param(NumericBoundsCase("LONG", -10, 10, 5), id="glong"),
    pytest.param(NumericBoundsCase("ULONG", 1, 10, 5), id="gulong"),
    pytest.param(NumericBoundsCase("INT64", -(2**40), 2**40, 123), id="gint64"),
    pytest.param(NumericBoundsCase("UINT64", 1, 2**40, 123), id="guint64"),
    pytest.param(NumericBoundsCase("FLOAT", -1.5, 2.5, 1.25), id="gfloat"),
    pytest.param(NumericBoundsCase("DOUBLE", -1.5, 2.5, 1.25), id="gdouble"),
]


@dataclass
class NumericPSpecInfo:
    minimum: int | float
    maximum: int | float
    default_value: int | float


def read_numeric_pspec(pointer: int) -> NumericPSpecInfo:
    from ginext import private

    return NumericPSpecInfo(**private.param_spec_numeric_info(pointer))


@dataclass
class PSpecInfo:
    pointer: int
    name: str
    nick: str | None
    blurb: str | None
    flags: int
    value_type: int
    value_type_name: str
    owner_type: int

    def has_flag(self, flag: int) -> bool:
        return bool(self.flags & flag)


@pytest.fixture(scope="session")
def gobject_module() -> types.ModuleType:
    from ginext.gobject import gobjectclass as mod

    return mod


@pytest.fixture(scope="session")
def Property(gobject_module: types.ModuleType) -> object:
    return gobject_module.Property


@pytest.fixture(scope="session")
def GObject(gobject_module: types.ModuleType) -> type[_GObjectBase]:
    return gobject_module.GObject


@pytest.fixture(scope="session")
def GType() -> type[GTypeClass]:
    from ginext.gobject.gtype import GType

    return GType


@pytest.fixture(scope="session")
def GLib() -> types.ModuleType:
    from ginext import GLib

    return GLib


@pytest.fixture(scope="session")
def Gio() -> types.ModuleType:
    from ginext import Gio

    return Gio


@pytest.fixture
def cancellable(Gio: types.ModuleType) -> object:
    return Gio.Cancellable()


@pytest.fixture
def pspec_info() -> Callable[[int], PSpecInfo]:
    def _read(pointer: int) -> PSpecInfo:
        from ginext import private

        return PSpecInfo(**private.param_spec_info(pointer))

    return _read


@pytest.fixture
def pspec_default() -> Callable[[int], object]:
    def _read(pspec_pointer: int) -> object:
        from ginext import private

        return private.param_spec_default_value(pspec_pointer)

    return _read


_type_name_counter = itertools.count()


_SKIP_BY_PATH: dict[str, str] = {}


_XFAIL_BY_NODE = {
    "test_no_gi_on_hot_path.py::test_descriptor_build_does_call_gi": (
        "plan/build stats split is not exposed in the current ginext slice"
    ),
}


_GI_TESTS_MODULES = {
    "test_gi_marshalling_tests",
    "test_regress",
    "test_regress_unix",
    "gi_conformance",
}


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    skip_gi_tests = None
    if GI_TESTS_BUILDDIR is None:
        skip_gi_tests = pytest.mark.skip(
            reason="gi-tests not built; rerun with `make test` "
            "(or `meson configure -Dbuild_gi_tests=true`)"
        )

    for item in items:
        path = item.path.as_posix()
        if "/gtk3/" in path:
            item.add_marker(pytest.mark.gtk3)
            item.add_marker(pytest.mark.xdist_group("gtk3"))
        if "/gtk4/" in path:
            item.add_marker(pytest.mark.gtk4)
            item.add_marker(pytest.mark.xdist_group("gtk4"))
        for suffix, reason in _SKIP_BY_PATH.items():
            if path.endswith(suffix):
                item.add_marker(pytest.mark.skip(reason=reason))
                break
        for suffix, reason in _XFAIL_BY_NODE.items():
            if item.nodeid.endswith(suffix):
                item.add_marker(pytest.mark.xfail(reason=reason, strict=False))
                break
        if skip_gi_tests is not None and any(
            module in item.nodeid for module in _GI_TESTS_MODULES
        ):
            item.add_marker(skip_gi_tests)


@pytest.fixture(autouse=True)
def _reset_scoped_defaults_state(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Generator[None]:
    path = request.node.path.as_posix()
    needs_defaults = "/defaults/" in path
    needs_namespace = "/namespace/" in path
    needs_features = "/features/" in path
    if not (needs_defaults or needs_namespace or needs_features):
        yield
        return

    from ginext import defaults

    # Isolate the resolution state per test. These tests poke app-resolution
    # internals (env vars, but also inference seams like _main_package_for_test
    # that the input keys can't see), so snapshot every resolution cache and the
    # require() registry, start each test cold, and restore afterwards. Crucially
    # this does NOT tear down namespace/class singletons — their identity must
    # stay stable for code holding references to them (the old reset_caches did,
    # which is why it was removed).
    for var in _GINEXT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    saved = (
        defaults._installed_cache,
        defaults._installed_cache_key,
        defaults._project_defaults_cache,
        defaults._project_defaults_cache_key,
        defaults._required_versions_cache,
    )
    defaults._installed_cache = None
    defaults._installed_cache_key = None
    defaults._project_defaults_cache = None
    defaults._project_defaults_cache_key = None
    defaults._required_versions_cache = {}
    yield
    (
        defaults._installed_cache,
        defaults._installed_cache_key,
        defaults._project_defaults_cache,
        defaults._project_defaults_cache_key,
        defaults._required_versions_cache,
    ) = saved


@pytest.fixture(autouse=True)
def _force_native_signal_surface(
    request: pytest.FixtureRequest,
) -> Generator[None]:
    path = request.node.path.as_posix()
    if "/features/" in path:
        yield
        return

    import ginext.features as features

    was = features.is_enabled(features.PYGOBJECT_COMPAT)
    features.set_enabled(features.PYGOBJECT_COMPAT, False)
    try:
        yield
    finally:
        features.set_enabled(features.PYGOBJECT_COMPAT, was)


CALL_MODES = ["ginext"]


@pytest.fixture(params=CALL_MODES)
def call_mode(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def unique_type_name() -> Callable[[str], str]:
    def _next(prefix: str = "GinextPropTest") -> str:
        return f"{prefix}{next(_type_name_counter):04d}"

    return _next


@pytest.fixture
def make_subclass(
    GObject: type[_GObjectBase], unique_type_name: Callable[[str], str]
) -> _MakeSubclass:
    def _make(
        fields: dict[str, tuple[type, object]] | None = None,
        *,
        base: type | None = None,
        prefix: str = "Sub",
        attrs: dict[str, object] | None = None,
    ) -> type:
        base = base or GObject
        fields = fields or {}
        annotations = {name: typ for name, (typ, _) in fields.items()}
        body: dict[str, object] = {"__annotations__": annotations}
        for name, (_, prop) in fields.items():
            body[name] = prop
        if attrs:
            body.update(attrs)
        return type(base)(unique_type_name(prefix), (base,), body)

    return _make


@pytest.fixture
def make_property_class(
    make_subclass: _MakeSubclass, Property: object
) -> _MakePropertyClass:
    def _make(
        annotation: type,
        *,
        name: str = "x",
        prefix: str = "Prop",
        base: type | None = None,
        **property_kwargs: object,
    ) -> type:
        return make_subclass(
            {name: (annotation, cast("_PropertyFactory", Property)(**property_kwargs))},
            base=base,
            prefix=prefix,
        )

    return _make
