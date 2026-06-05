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

"""GParamSpec coverage — wholly introspection-driven, no per-pspec wiring.

goi auto-discovers `list_properties` (and the rest of GObjectClass)
from `gi_object_info_get_class_struct(...)` at class build time and
installs them as Python classmethods. The returned `GParamSpec*` array
flows through the standard return marshaller and lazy-binds to the
matching auto-built `GObject.ParamSpec*` subclass — `.name`, `.flags`,
`.value_type`, `.owner_type` come from GIR-declared fields on
`ParamSpec`; `.minimum`, `.maximum`, `.default_value` come from fields
on subclasses (`ParamSpecInt`, `ParamSpecDouble`, ...).

The shape mirrors PyGObject's tests/test_properties.py expectations
(name/nick/blurb/flags/default_value/minimum/maximum) but drops the
unittest.TestCase machinery in favour of pytest fixtures and
parametrisation.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from ginext.namespace import Namespace
from ginext.tests.typelib.support import (
    assert_gobject_class_mro,
    open_namespace_for_test,
)

if TYPE_CHECKING:
    from collections.abc import Generator


# list_properties() no longer segfaults (the GParamSpec array-element
# double-unref was fixed in marshal/c-array.c — see project_list_properties_crash),
# so the file runs and 30 tests pass for real. The remaining gap is *typed*
# ParamSpec subclass introspection: ginext hands back a generic ParamSpec
# wrapper rather than ParamSpecInt/String/Object/etc., so subclass MRO,
# numeric min/max bounds, default_value, value_type/owner_type GType wrappers,
# the name/nick/blurb accessors, and dir() of subclass attrs are not yet
# populated. Tests that depend on that are marked xfail until the typed
# wrappers land.
typed_paramspec_pending = pytest.mark.xfail(
    reason="typed ParamSpec subclass introspection (min/max, default, "
    "value_type, accessors, MRO) not yet implemented",
    strict=False,
)


@pytest.fixture
def old_signal_api() -> Generator[None, None, None]:
    """Enable the pygobject-style string `.connect()` API for tests that use
    it. OLD_SIGNAL_API is off by default (native ginext uses the new signal
    API), so a test driving `obj.connect("notify::...", ...)` must opt in
    explicitly rather than relying on another test having left it on."""
    from ginext import features

    features.set_enabled(features.OLD_SIGNAL_API, True)
    try:
        yield
    finally:
        features.set_enabled(features.OLD_SIGNAL_API, False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def Gio(call_mode: str) -> Namespace:
    return open_namespace_for_test(call_mode, "Gio", "2.0")


@pytest.fixture
def GIM(call_mode: str) -> Namespace:
    return open_namespace_for_test(call_mode, "GIMarshallingTests", "1.0")


@pytest.fixture
def simple_action_specs(Gio: Namespace) -> list[object]:
    return Gio.SimpleAction.list_properties()  # type: ignore[no-any-return]


@pytest.fixture
def props_object_specs(GIM: Namespace) -> list[object]:
    return GIM.PropertiesObject.list_properties()  # type: ignore[no-any-return]


def test_properties_object_mro_uses_live_gobject_object(GIM: Namespace) -> None:
    assert_gobject_class_mro(GIM.PropertiesObject)


def find(specs: list[object], name: str) -> object:
    for s in specs:
        if getattr(s, "name") == name:
            return s
    raise AssertionError(f"no property named {name!r}")


# ---------------------------------------------------------------------------
# list_properties shape
# ---------------------------------------------------------------------------


def test_list_properties_returns_list(simple_action_specs: list[object]) -> None:
    assert isinstance(simple_action_specs, list)
    assert len(simple_action_specs) > 0


def test_list_properties_names_match_known_set(simple_action_specs: list[object]) -> None:
    """Gio.SimpleAction's introspected properties — a stable set we can pin."""
    names = sorted(getattr(s, "name") for s in simple_action_specs)
    assert names == sorted(["enabled", "name", "parameter-type", "state", "state-type"])


@typed_paramspec_pending
def test_returned_objects_are_paramspec_subclasses(
    Gio: Namespace, simple_action_specs: list[object]
) -> None:
    """Every entry should be an instance of GObject.ParamSpec — auto-bound
    by goi's wrap path looking up the runtime GType in the registry."""
    GObject = open_namespace_for_test("auto", "GObject", "2.0")
    for s in simple_action_specs:
        assert isinstance(s, GObject.ParamSpec), (s, type(s).__mro__)


# ---------------------------------------------------------------------------
# ParamSpec field/method coverage (drives the introspected getters)
# ---------------------------------------------------------------------------


@typed_paramspec_pending
@pytest.mark.parametrize("attr", ["name", "nick", "blurb"])
def test_string_method_accessor_returns_str_or_none(
    simple_action_specs: list[object], attr: str
) -> None:
    spec = simple_action_specs[0]
    fn = getattr(spec, f"get_{attr}")
    val = fn()
    assert val is None or isinstance(val, str)


@typed_paramspec_pending
def test_field_name_matches_get_name(simple_action_specs: list[object]) -> None:
    """`.name` (field) and `.get_name()` (method) must agree — both come
    from GIR, so this catches a class-builder regression where one path
    silently breaks."""
    for s in simple_action_specs:
        assert getattr(s, "name") == getattr(s, "get_name")()


@typed_paramspec_pending
def test_value_type_is_gtype_wrapper(simple_action_specs: list[object]) -> None:
    enabled = find(simple_action_specs, "enabled")
    # value_type should be a GType wrapper (not a raw int) — hits the
    # GTYPE-tag field path.
    assert hasattr(getattr(enabled, "value_type"), "name")
    assert getattr(getattr(enabled, "value_type"), "name") == "gboolean"


@typed_paramspec_pending
def test_owner_type_points_to_declaring_class(simple_action_specs: list[object]) -> None:
    enabled = find(simple_action_specs, "enabled")
    assert getattr(getattr(enabled, "owner_type"), "name") == "GSimpleAction"


@typed_paramspec_pending
def test_flags_is_int_bitmask(simple_action_specs: list[object]) -> None:
    """`.flags` is exposed as a `<type name="ParamFlags">` (interface
    tag) in GIR — hits the field-lookup interface/flags branch."""
    spec = simple_action_specs[0]
    assert isinstance(getattr(spec, "flags"), int)
    assert getattr(spec, "flags") > 0


# ---------------------------------------------------------------------------
# Numeric subclass fields (ParamSpecInt etc.) — minimum/maximum/default_value
# ---------------------------------------------------------------------------


@typed_paramspec_pending
@pytest.mark.parametrize(
    "name, expected_class, expected_min, expected_max",
    [
        ("some-int", "ParamSpecInt", -(2**31), 2**31 - 1),
        ("some-uint", "ParamSpecUInt", 0, 2**32 - 1),
        ("some-int64", "ParamSpecInt64", -(2**63), 2**63 - 1),
        ("some-uint64", "ParamSpecUInt64", 0, 2**64 - 1),
    ],
)
def test_integer_subclass_min_max_match_c_limits(
    props_object_specs: list[object],
    name: str,
    expected_class: str,
    expected_min: int,
    expected_max: int,
) -> None:
    spec = find(props_object_specs, name)
    assert type(spec).__name__ == expected_class
    assert getattr(spec, "minimum") == expected_min
    assert getattr(spec, "maximum") == expected_max
    assert getattr(spec, "default_value") == 0


@typed_paramspec_pending
@pytest.mark.parametrize(
    "name, cls", [("some-float", "ParamSpecFloat"), ("some-double", "ParamSpecDouble")]
)
def test_float_subclass_min_max_are_floats(
    props_object_specs: list[object], name: str, cls: str
) -> None:
    spec = find(props_object_specs, name)
    assert type(spec).__name__ == cls
    assert isinstance(getattr(spec, "minimum"), float)
    assert isinstance(getattr(spec, "maximum"), float)
    assert getattr(spec, "minimum") < 0 < getattr(spec, "maximum")
    assert getattr(spec, "default_value") == 0.0


@typed_paramspec_pending
def test_string_subclass_default_value_is_none_or_str(
    props_object_specs: list[object],
) -> None:
    spec = find(props_object_specs, "some-string")
    assert type(spec).__name__ == "ParamSpecString"
    dv = getattr(spec, "get_default_value")()
    assert dv is None or isinstance(dv, str)


# ---------------------------------------------------------------------------
# Inheritance / type accessor sanity
# ---------------------------------------------------------------------------


@typed_paramspec_pending
def test_paramspec_subclass_mro_includes_paramspec(
    props_object_specs: list[object],
) -> None:
    GObject = open_namespace_for_test("auto", "GObject", "2.0")
    int_spec = find(props_object_specs, "some-int")
    assert GObject.ParamSpec in type(int_spec).__mro__


def test_classmethod_dispatch_does_not_require_instance(Gio: Namespace) -> None:
    """list_properties is installed via classmethod() on the class — no
    instance materialisation should be needed to call it."""
    specs = Gio.SimpleAction.list_properties()
    assert specs  # non-empty


def test_interface_methods_are_found_on_implementing_object_instances(Gio: Namespace) -> None:
    group = Gio.SimpleActionGroup()
    action = Gio.SimpleAction.new("demo", None)

    group.add_action(action)
    looked_up = group.lookup_action("demo")

    assert looked_up is not None
    assert looked_up.get_name() == "demo"


@pytest.mark.xfail(
    reason="interface methods are callable but not yet listed in __dir__ "
    "(see test_interface_methods_are_found_on_implementing_object_instances "
    "which calls add_action directly and passes)",
    strict=False,
)
def test_dir_includes_interface_methods(Gio: Namespace) -> None:
    names = set(dir(Gio.SimpleActionGroup()))
    assert "add_action" in names
    assert "lookup_action" in names


def test_notify_signal_marshals_object_and_paramspec_args(
    Gio: Namespace, old_signal_api: None
) -> None:
    action = Gio.SimpleAction.new("demo", None)
    seen: dict[str, object] = {}

    def on_notify(obj: object, pspec: object) -> None:
        seen["obj"] = obj
        seen["pspec"] = pspec

    action.connect("notify::enabled", on_notify)
    action.set_enabled(False)

    assert seen["obj"] is action
    assert seen["pspec"] is not None
    assert "ParamSpec" in type(seen["pspec"]).__name__


@pytest.mark.xfail(
    sys.platform == "win32",
    reason="GApplication.run ignores the passed argv on Windows and parses the "
    "real process command line via GetCommandLineW, so the injected "
    "--version option is never seen",
    strict=True,
)
def test_command_line_options_dict_returns_variant_dict(
    Gio: Namespace, old_signal_api: None
) -> None:
    seen: dict[str, object] = {}
    # Per-worker-unique app id: xdist runs tests in parallel processes
    # that share the user's DBus session bus. A fixed name (e.g.
    # "org.example.goi.optionsdict") races with itself across workers,
    # the second registration fails with NameInUseOnConnection, and the
    # `command-line` handler never fires. PID makes the name unique
    # per process and survives test-order shuffles.
    import os

    app_id = f"org.example.goi.optionsdict.p{os.getpid()}"
    app = Gio.Application.new(
        app_id,
        Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
    )
    app.add_main_option("version", ord("v"), 0, 0, "version", None)

    def on_cli(_app: object, cmd: object) -> int:
        options = getattr(cmd, "get_options_dict")()
        seen["type"] = type(options).__name__
        seen["has_version"] = getattr(options, "contains")("version")
        return 0

    app.connect("command-line", on_cli)
    assert app.run(["prog", "--version"]) == 0
    assert seen["type"] == "VariantDict"
    assert seen["has_version"] is True


@pytest.mark.xfail(
    reason="G_TYPE_STRV (gchar**) property set/get round-trip not yet implemented",
    strict=False,
)
def test_strv_property_round_trip(GIM: Namespace) -> None:
    """G_TYPE_STRV (gchar**) properties must accept any Python sequence
    of str (drawing-run uses this via Gtk.AboutDialog(authors=[...])).
    Reads come back as a list of str. None clears the value."""
    obj = GIM.PropertiesObject()

    obj.set_property("some-strv", ["alice", "bob"])
    assert obj.get_property("some-strv") == ["alice", "bob"]

    # Tuples and other sequences are accepted.
    obj.set_property("some-strv", ("carol", "dave"))
    assert obj.get_property("some-strv") == ["carol", "dave"]

    # None clears.
    obj.set_property("some-strv", None)
    assert obj.get_property("some-strv") is None

    # Non-str items are rejected with a clear TypeError.
    with pytest.raises(TypeError, match="not a str"):
        obj.set_property("some-strv", [1, 2])


# ---------------------------------------------------------------------------
# Cross-class inheritance / referencing — modelled on PyGObject's
# tests/test_gobject.py::test_list_properties.
# ---------------------------------------------------------------------------


def test_subclass_inherits_superclass_properties(Gio: Namespace) -> None:
    """A concrete subclass should expose at least its parent's property
    set. Gio.SimpleActionGroup → Gio.ActionMap is interface-typed in
    GIR, so we use a class/class pair: Gio.MenuItem doesn't add props
    over GObject.Object, but Gio.Application does (over GObject.Object).
    Use SimpleAction self-comparison plus a known-property check
    instead — every spec we see comes from a class-struct-walk that
    libgobject populates from g_object_class_install_property up the
    chain."""
    impl = {getattr(p, "name") for p in Gio.SimpleAction.list_properties()}
    assert "enabled" in impl
    assert "name" in impl


@typed_paramspec_pending
def test_property_value_type_points_to_other_gir_class(Gio: Namespace) -> None:
    """Gio.FileIcon's `file` property should have value_type = Gio.File's
    GType. Both sides come from introspection, so we compare GType
    objects by name (the wrapper's __eq__ semantics are out of scope)."""
    spec = find(Gio.FileIcon.list_properties(), "file")
    assert (
        getattr(getattr(spec, "value_type"), "name") == Gio.File.__goi_gtype_name__
        if hasattr(Gio.File, "__goi_gtype_name__")
        else getattr(getattr(spec, "value_type"), "name") == "GFile"
    )


# ---------------------------------------------------------------------------
# `dir()` exposes the common ParamSpec surface — mirrors PyGObject's
# tests/test_properties.py::test_param_spec_dir.
# ---------------------------------------------------------------------------


@typed_paramspec_pending
def test_dir_lists_common_paramspec_attrs(props_object_specs: list[object]) -> None:
    spec = find(props_object_specs, "some-float")
    attrs = set(dir(spec))
    expected = {
        "name",
        "nick",
        "blurb",
        "flags",
        "default_value",
        "minimum",
        "maximum",
        "value_type",
        "owner_type",
        "get_name",
        "get_nick",
        "get_blurb",
        "get_default_value",
    }
    missing = expected - attrs
    assert not missing, f"missing on dir(spec): {missing}"


# ---------------------------------------------------------------------------
# A non-GObject argument should not crash list_properties — goi routes
# the classmethod through g_type_class_ref which asserts G_TYPE_IS_OBJECT,
# so calling list_properties on a non-GObject GIR class must raise rather
# than abort. Modelled on PyGObject's "for obj in [..., 0, object()]" loop.
# ---------------------------------------------------------------------------


def test_list_properties_on_non_object_raises(Gio: Namespace) -> None:
    """`Gio.DBusError` is an enum (not a GObject) — list_properties on
    it should raise rather than crash."""
    with pytest.raises((TypeError, RuntimeError, AttributeError)):
        Gio.DBusError.list_properties()
