# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Generator tests driven by a self-contained synthetic GIR fixture.

ginext_stubgen parses GIR XML and emits no runtime dependency, so these tests
need neither a built ginext nor installed typelibs — just a .gir on disk.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ginext_stubgen import Callable, Emitter, Klass, Namespace, Param, generate

if TYPE_CHECKING:
    from pathlib import Path

# A minimal but representative namespace: an enum, and a GObject class with a
# keyword-named arg, multiple out-params, and two signals (one void/no-arg, one
# with a typed arg and a non-void return).
TESTLIB_GIR = """<?xml version="1.0"?>
<repository xmlns="http://www.gtk.org/introspection/core/1.0"
            xmlns:c="http://www.gtk.org/introspection/c/1.0"
            xmlns:glib="http://www.gtk.org/introspection/glib/1.0">
  <namespace name="Testlib" version="1.0" c:identifier-prefixes="Test">
    <enumeration name="Direction" glib:type-name="TestDirection">
      <member name="up" value="0" c:identifier="TEST_DIRECTION_UP"/>
      <member name="down" value="1" c:identifier="TEST_DIRECTION_DOWN"/>
    </enumeration>
    <class name="Widget" c:type="TestWidget" glib:type-name="TestWidget"
           glib:get-type="test_widget_get_type" parent="GObject.Object">
      <property name="title" writable="1" transfer-ownership="none">
        <type name="utf8" c:type="gchar*"/>
      </property>
      <property name="count" readable="1" transfer-ownership="none">
        <type name="gint" c:type="gint"/>
      </property>
      <method name="set_value" c:identifier="test_widget_set_value">
        <return-value transfer-ownership="none"><type name="none"/></return-value>
        <parameters>
          <parameter name="in" transfer-ownership="none"><type name="gint"/></parameter>
        </parameters>
      </method>
      <method name="get_range" c:identifier="test_widget_get_range">
        <return-value transfer-ownership="none"><type name="gboolean"/></return-value>
        <parameters>
          <parameter name="min" direction="out" transfer-ownership="none"><type name="gint"/></parameter>
          <parameter name="max" direction="out" transfer-ownership="none"><type name="gint"/></parameter>
        </parameters>
      </method>
      <method name="load_async" c:identifier="test_widget_load_async">
        <return-value transfer-ownership="none"><type name="none"/></return-value>
        <parameters>
          <parameter name="io_priority" transfer-ownership="none"><type name="gint"/></parameter>
          <parameter name="cancellable" nullable="1" allow-none="1" transfer-ownership="none">
            <type name="Gio.Cancellable"/>
          </parameter>
          <parameter name="callback" nullable="1" allow-none="1" transfer-ownership="none">
            <type name="Gio.AsyncReadyCallback"/>
          </parameter>
        </parameters>
      </method>
      <method name="load_finish" c:identifier="test_widget_load_finish">
        <return-value transfer-ownership="none"><type name="utf8" c:type="gchar*"/></return-value>
        <parameters>
          <parameter name="result" transfer-ownership="none"><type name="Gio.AsyncResult"/></parameter>
        </parameters>
      </method>
      <glib:signal name="clicked" when="last" action="1">
        <return-value transfer-ownership="none"><type name="none"/></return-value>
      </glib:signal>
      <glib:signal name="activate-link" when="last">
        <return-value transfer-ownership="none"><type name="gboolean"/></return-value>
        <parameters>
          <parameter name="uri" transfer-ownership="none"><type name="utf8"/></parameter>
        </parameters>
      </glib:signal>
    </class>
  </namespace>
</repository>
"""


@pytest.fixture(scope="module")
def gir_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("gir") / "Testlib-1.0.gir"
    path.write_text(TESTLIB_GIR, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def native(gir_path: Path) -> str:
    _name, text = generate(gir_path, mode="native")
    return text


@pytest.fixture(scope="module")
def compat(gir_path: Path) -> str:
    _name, text = generate(gir_path, mode="gi")
    return text


def test_output_parses(native: str) -> None:
    ast.parse(native)  # raises on malformed output


def test_header_has_override_directive(native: str) -> None:
    assert '# mypy: disable-error-code="override,type-arg,misc,valid-type"' in native


def test_checked_in_gobject_stub_exposes_notify_as_detailed_signal() -> None:
    stub_path = (
        Path(__file__).resolve().parents[2]
        / "ginext-stubs"
        / "ginext-stubs"
        / "GObject.pyi"
    )
    if not stub_path.exists():
        pytest.skip("generated ginext-stubs/GObject.pyi absent (run `make stubs`)")
    text = stub_path.read_text(encoding="utf-8")

    assert "    notify: DetailedSignal[Self, [ParamSpec], None]" in text
    assert "    def notify(self, property_name: str) -> None:" not in text
    assert "    def __getitem__(self, detail: str) ->" not in text


class TestNativeSignals:
    """Native mode: signals are typed descriptor attributes, not string
    connect overloads. A method-backed signal is callable (_SignalMethod);
    a plain signal is not (_Signal)."""

    def test_action_signal_without_method_backing_is_plain_signal(self, native: str) -> None:
        # clicked is action="1", but without a real GIR method backing it
        # stays a plain Signal.
        assert "    clicked: Signal[Self, [], None]" in native

    def test_plain_signal_is_signal(self, native: str) -> None:
        # activate-link is not an action signal: connect/emit only
        assert "    activate_link: Signal[Self, [str], bool]" in native

    def test_signal_helpers_emitted(self, native: str) -> None:
        assert "class Signal(Generic[_SigO, _SigP, _SigR]):" in native
        assert "class SignalMethod(Signal[_SigO, _SigP, _SigR]):" in native
        assert "ParamSpec as _ParamSpec" in native  # aliased to avoid GObject clash

    def test_no_string_connect_overloads_in_native(self, native: str) -> None:
        assert "def connect(self, signal: Literal[" not in native
        assert "def connect(self, signal: str, handler:" not in native

    def test_do_handlers_still_emitted(self, native: str) -> None:
        assert "def do_clicked(self) -> None: ..." in native


class TestCompatSignals:
    """gi (pygobject-compat) mode keeps the legacy string-keyed connect/emit
    overloads."""

    def test_connect_overload_no_args(self, compat: str) -> None:
        assert (
            'def connect(self, signal: Literal["clicked"], '
            "handler: Callable[[Self], None], *args: Any) -> int: ..." in compat
        )

    def test_connect_overload_typed_handler(self, compat: str) -> None:
        assert (
            'def connect(self, signal: Literal["activate-link"], '
            "handler: Callable[[Self, str], bool], *args: Any) -> int: ..." in compat
        )

    def test_emit_overload_carries_return_and_params(self, compat: str) -> None:
        assert (
            'def emit(self, signal: Literal["activate-link"], uri: str) -> bool: ...'
            in compat
        )

    def test_generic_catch_all_present(self, compat: str) -> None:
        assert (
            "def connect(self, signal: str, handler: Callable[..., Any], "
            "*args: Any) -> int: ..." in compat
        )

    def test_overloads_are_decorated(self, compat: str) -> None:
        lines = compat.splitlines()
        for i, line in enumerate(lines):
            if "def connect(self, signal:" in line or "def emit(self, signal:" in line:
                assert lines[i - 1].strip() == "@overload", line


class TestCallables:
    def test_keyword_arg_sanitised(self, native: str) -> None:
        # arg literally named `in` becomes `in_`
        assert "def set_value(self, in_: int) -> None" in native

    def test_out_params_folded_into_tuple(self, native: str) -> None:
        # gboolean return + two out gint => tuple[bool, int, int]
        assert "def get_range(self) -> tuple[bool, int, int]: ..." in native

    def test_enum_is_intenum(self, native: str) -> None:
        assert "class Direction(IntEnum):" in native
        assert "UP = 0" in native
        assert "DOWN = 1" in native

    def test_native_async_method_emits_awaitable_overload(self, native: str) -> None:
        assert (
            "def load_async(self, io_priority: int, cancellable: Gio.Cancellable | None = ..., "
            "callback: None = ...) -> Awaitable[str]: ..." in native
        )

    def test_native_async_method_emits_callback_overload(self, native: str) -> None:
        assert (
            "def load_async(self, io_priority: int, cancellable: Gio.Cancellable | None = ..., "
            "callback: Gio.AsyncReadyCallback = ...) -> None: ..." in native
        )


class TestConstruction:
    def test_init_is_typed_keyword_only(self, native: str) -> None:
        # writable `title` becomes a keyword-only param; **kwargs keeps
        # inherited/unlisted props usable.
        assert (
            "def __init__(self, *, title: str = ..., **kwargs: Any) -> None: ..."
            in native
        )

    def test_readonly_prop_excluded_from_init(self, native: str) -> None:
        # `count` is read-only -> not a constructor keyword
        assert "count: int = ..." not in native

    def test_properties_are_attributes(self, native: str) -> None:
        # both readable and writable props remain attribute annotations
        assert "    title: str" in native
        assert "    count: int" in native


def _model_klass() -> Klass:
    # A class implementing Gio.ListModel with item-typed members.
    return Klass(
        kind="class",
        name="MyModel",
        parents=["GObject.Object", "Gio.ListModel"],
        methods=[
            Callable(
                name="get_item",
                params=[Param("position", "int", "in", False, False)],
                return_expr="GObject.Object | None",
                out_exprs=[],
            ),
            Callable(
                name="get_item_type",
                params=[],
                return_expr="type | GObject.Type",
                out_exprs=[],
            ),
            Callable(
                name="get_model",
                params=[],
                return_expr="Gio.ListModel | None",
                out_exprs=[],
            ),
        ],
    )


class TestItemTypeGeneric:
    def setup_method(self) -> None:
        self.klass = _model_klass()
        Emitter(Namespace(name="Gtk", version="4.0"), mode="native")._apply_item_type(
            self.klass, "_T"
        )

    def test_listmodel_base_parameterized(self) -> None:
        assert "Gio.ListModel[_T]" in self.klass.parents

    def test_item_return_becomes_typevar(self) -> None:
        assert self.klass.methods[0].return_expr == "_T | None"

    def test_get_item_type_becomes_type_of_t(self) -> None:
        assert self.klass.methods[1].return_expr == "type[_T]"

    def test_wrapped_model_parameterized(self) -> None:
        assert self.klass.methods[2].return_expr == "Gio.ListModel[_T] | None"


class TestItemTypeConcrete:
    def setup_method(self) -> None:
        self.klass = _model_klass()
        Emitter(Namespace(name="Gtk", version="4.0"), mode="native")._apply_item_type(
            self.klass, "StringObject"
        )

    def test_listmodel_base_concrete(self) -> None:
        assert "Gio.ListModel[StringObject]" in self.klass.parents

    def test_item_return_concrete(self) -> None:
        assert self.klass.methods[0].return_expr == "StringObject | None"

    def test_concrete_not_generic_on_wrapped_model(self) -> None:
        # only the generic case parameterizes the wrapped Gio.ListModel accessor
        assert self.klass.methods[2].return_expr == "Gio.ListModel | None"


class TestItemTypeGioNamespace:
    def test_same_namespace_listmodel_is_bare(self) -> None:
        klass = Klass(
            kind="class",
            name="ListStore",
            parents=["GObject.Object", "ListModel"],
            methods=[],
        )
        Emitter(Namespace(name="Gio", version="2.0"), mode="native")._apply_item_type(
            klass, "_T"
        )
        # within Gio's own stub, ListModel is referenced bare
        assert "ListModel[_T]" in klass.parents
        assert "Gio.ListModel[_T]" not in klass.parents


class TestModes:
    def test_native_import_root(self, native: str) -> None:
        assert "from ginext import GObject" in native
        assert "from gi.repository import" not in native

    def test_gi_import_root(self, compat: str) -> None:
        assert "from gi.repository import GObject" in compat
        assert "from ginext import" not in compat
