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

import gc

import pytest

from ginext.namespace import Namespace
from ginext.tests.gi_test_utils import load_test_namespace


@pytest.fixture(scope="module")
def gm() -> Namespace:
    return load_test_namespace("GIMarshallingTests")


@pytest.fixture(scope="module")
def regress() -> Namespace:
    return load_test_namespace("Regress")


@pytest.fixture(scope="module")
def gio() -> Namespace:
    return load_test_namespace("Gio", "2.0")


def test_boxed_struct_default_constructor_and_fields(gm: Namespace) -> None:
    struct = gm.BoxedStruct()

    assert isinstance(struct, gm.BoxedStruct)
    assert struct.long_ == 0
    assert struct.string_ is None
    assert struct.g_strv == []


def test_boxed_struct_named_constructor(gm: Namespace) -> None:
    struct = gm.BoxedStruct.new()

    assert isinstance(struct, gm.BoxedStruct)
    assert struct.long_ == 0
    assert struct.string_ is None


def test_boxed_struct_field_assignment(gm: Namespace) -> None:
    struct = gm.BoxedStruct()

    struct.long_ = 42
    struct.string_ = "hello"
    struct.g_strv = ["0", "1", "2"]

    assert struct.long_ == 42
    assert struct.string_ == "hello"
    assert struct.g_strv == ["0", "1", "2"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("hello", "hello"),
        ("", ""),
        ("non-ascii: cafe", "non-ascii: cafe"),
        (None, None),
    ],
)
def test_boxed_struct_utf8_field_round_trip(
    gm: Namespace, value: str | None, expected: str | None
) -> None:
    struct = gm.BoxedStruct()

    struct.string_ = value

    assert struct.string_ == expected


@pytest.mark.parametrize(
    "arg_enum",
    ["NONE", "STRING", "INT", "FILENAME", "STRING_ARRAY", "DOUBLE"],
)
def test_option_entry_arg_field_accepts_enum_int(gio: Namespace, arg_enum: str) -> None:
    from ginext import GLib

    option_entry = GLib.OptionEntry()
    value = int(getattr(GLib.OptionArg, arg_enum))

    option_entry.arg = value

    assert option_entry.arg == value


def test_option_entry_arg_field_rejects_non_int() -> None:
    from ginext import GLib

    option_entry = GLib.OptionEntry()

    with pytest.raises(TypeError, match="integer"):
        option_entry.arg = "STRING"  # tests that str value is rejected by C marshaller


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("verbose", "verbose"),
        ("", ""),
        ("non-ascii: cafe", "non-ascii: cafe"),
        (None, None),
    ],
    ids=["plain", "empty", "non-ascii", "none"],
)
def test_option_entry_long_name_round_trip(
    value: str | None, expected: str | None
) -> None:
    from ginext import GLib

    option_entry = GLib.OptionEntry()
    option_entry.long_name = value

    assert option_entry.long_name == expected


def test_option_entry_long_name_overwrite_no_leak() -> None:
    from ginext import GLib

    option_entry = GLib.OptionEntry()

    for value in ("a", "bb", "ccc", "dddd"):
        option_entry.long_name = value

    assert option_entry.long_name == "dddd"


def test_option_entry_long_name_rejects_non_str() -> None:
    from ginext import GLib

    option_entry = GLib.OptionEntry()

    with pytest.raises(TypeError, match="expected str"):
        option_entry.long_name = 42  # tests that int value is rejected by str field


def test_option_entry_arg_data_accepts_none() -> None:
    from ginext import GLib

    option_entry = GLib.OptionEntry()

    option_entry.arg_data = None


def test_option_entry_arg_data_rejects_non_none() -> None:
    from ginext import GLib

    option_entry = GLib.OptionEntry()

    with pytest.raises(TypeError, match="None"):
        option_entry.arg_data = 42


def test_boxed_struct_instance_method(gm: Namespace) -> None:
    struct = gm.BoxedStruct()
    struct.long_ = 42

    assert struct.inv() is None


def test_boxed_struct_return_function(gm: Namespace) -> None:
    struct = gm.boxed_struct_returnv()

    assert isinstance(struct, gm.BoxedStruct)
    assert struct.long_ == 42
    assert struct.string_ == "hello"
    assert struct.g_strv == ["0", "1", "2"]


def test_boxed_struct_type_function_return(gm: Namespace) -> None:
    struct = gm.BoxedStruct.returnv()

    assert isinstance(struct, gm.BoxedStruct)
    assert struct.long_ == 42


def test_boxed_struct_out(gm: Namespace) -> None:
    struct = gm.boxed_struct_out()

    assert isinstance(struct, gm.BoxedStruct)
    assert struct.long_ == 42


def test_boxed_struct_inout(gm: Namespace) -> None:
    struct = gm.BoxedStruct()
    struct.long_ = 42

    result = gm.boxed_struct_inout(struct)

    assert isinstance(result, gm.BoxedStruct)
    assert result.long_ == 0


def test_pointer_array_struct_with_uint8_array(gm: Namespace) -> None:
    struct = gm.PointerArrayStruct.with_uint8_array()

    assert isinstance(struct, gm.PointerArrayStruct)
    assert struct.array == list(map(ord, "0123456789"))


def test_regress_boxed_alternative_constructors(regress: Namespace) -> None:
    assert regress.TestBoxed.new_alternative_constructor1(5).some_int8 == 5
    assert regress.TestBoxed.new_alternative_constructor2(5, 3).some_int8 == 8
    assert regress.TestBoxed.new_alternative_constructor3("-3").some_int8 == -3


def test_regress_boxed_equality_method(regress: Namespace) -> None:
    boxed42 = regress.TestBoxed.new_alternative_constructor1(42)
    boxed5 = regress.TestBoxed.new_alternative_constructor1(5)
    boxed42_2 = regress.TestBoxed.new_alternative_constructor2(41, 1)

    assert boxed42.equals(boxed42) is True
    assert boxed42.equals(boxed42_2) is True
    assert boxed42.equals(boxed5) is False


def test_regress_boxed_c_copy_identity(regress: Namespace) -> None:
    boxed = regress.TestBoxedC()
    copied = boxed.copy()

    assert copied == boxed
    assert id(copied) != id(boxed)


def test_regress_boxed_c_wrapper_keeps_child_alive(regress: Namespace) -> None:
    wrapper = regress.TestBoxedCWrapper()
    obj = wrapper.get()

    assert obj.refcount == 2
    del wrapper
    gc.collect()
    assert obj.refcount == 1


def test_dbusnodeinfo_record_pointer_array_field(gio: Namespace) -> None:
    xml = """<node>
      <interface name="org.example.Foo">
        <method name="Ping"/>
      </interface>
      <interface name="org.example.Bar"/>
    </node>
    """

    node = gio.DBusNodeInfo.new_for_xml(xml)
    interfaces = node.interfaces

    assert [iface.name for iface in interfaces] == [
        "org.example.Foo",
        "org.example.Bar",
    ]
    assert interfaces[0].methods[0].name == "Ping"


def test_dbusnodeinfo_interfaces_empty_node(gio: Namespace) -> None:
    node = gio.DBusNodeInfo.new_for_xml("<node/>")

    assert node.interfaces == []


def test_dbusnodeinfo_child_wrappers_keep_parent_alive(gio: Namespace) -> None:
    xml = """<node>
      <interface name="org.example.Foo">
        <method name="Ping"/>
      </interface>
    </node>
    """

    interfaces = gio.DBusNodeInfo.new_for_xml(xml).interfaces
    gc.collect()

    assert interfaces[0].name == "org.example.Foo"
    assert interfaces[0].methods[0].name == "Ping"


def test_dbusmethodinfo_args_are_iterable_when_empty(gio: Namespace) -> None:
    xml = """<node>
      <interface name="org.example.Foo">
        <method name="Ping"/>
      </interface>
    </node>
    """

    node = gio.DBusNodeInfo.new_for_xml(xml)
    method = node.interfaces[0].methods[0]

    assert method.in_args == []
    assert method.out_args == []
