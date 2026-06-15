# Copyright 2026 Johan Dahlin
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

from gi.repository import GLib, GObject


def test_value(value: object) -> object:
    """Round-trip a Python value through GValue and back."""
    if isinstance(value, str):
        gtype = GObject.TYPE_STRING
    elif isinstance(value, bool):
        gtype = GObject.TYPE_BOOLEAN
    elif isinstance(value, int):
        gtype = GObject.TYPE_INT
    elif isinstance(value, float):
        gtype = GObject.TYPE_DOUBLE
    else:
        raise TypeError(f"unsupported type: {type(value)}")
    gv = GObject.Value(gtype, value)
    return gv.get_value()


def test_value_array(values: list) -> list:
    """Round-trip a list of Python values through GValueArray and back."""
    return [test_value(v) for v in values]


def test_gerror_exception(callable_: object) -> None:
    """Call callable_; re-raise GError if it raises one, else return None."""
    if not callable(callable_):
        raise TypeError("argument must be callable")
    try:
        result = callable_()
    except GLib.GError:
        raise
    except Exception:
        pass
    return None


def test_to_unichar_conv(value: object) -> int:
    """Convert a single character string to its Unicode code point."""
    if not isinstance(value, str):
        raise TypeError(f"expected str, got {type(value).__name__}")
    if len(value) != 1:
        raise TypeError(f"expected single character, got {len(value)!r}")
    return ord(value)


def constant_strip_prefix(name: str, prefix: str) -> str:
    """Strip a prefix from a constant name, stopping before a digit boundary.

    Strips prefix characters one at a time; stops if the remaining string
    would begin with a digit character.
    """
    stripped = 0
    for i, ch in enumerate(prefix):
        if i >= len(name) or name[i] != ch:
            break
        next_char = name[i + 1] if i + 1 < len(name) else ""
        if next_char.isdigit():
            break
        stripped = i + 1
    return name[stripped:]


def value_array_get_nth_type(value_or_array: object, index: int) -> object:
    item_types = getattr(value_or_array, "_ginext_compat_value_array_item_types", None)
    if item_types is None:
        holder = GObject.Value(GObject.ValueArray, value_or_array)
        item_types = getattr(holder, "_ginext_compat_value_array_item_types", ())
    return item_types[index]


def connectcallbacks(obj: GObject.Object) -> None:
    """Partial Python replacement for PyGObject's test helper extension."""
    obj.connect("test1", lambda source, data: None, "user-data")
    obj.connect("test2", lambda source, value: None)
    obj.connect("test3", lambda source, value: 20)
    obj.connect("test4", lambda source, *args: None)
    obj.connect("test-float", lambda source, value: value)
    obj.connect("test-double", lambda source, value: value)
    obj.connect(
        "test-int64",
        lambda source, value: value - 1 if value == 9223372036854775807 else value,
    )
    obj.connect("test-string", lambda source, value: value)
    obj.connect("test-object", lambda source, value: value)
    obj.connect(
        "test-paramspec",
        lambda source: GObject.param_spec_boolean(
            "test-param", "test", "test boolean", True, GObject.ParamFlags.READABLE
        ),
    )
    obj.connect("test-paramspec-in", lambda source, value: value)
    obj.connect("test-gvalue", lambda source, value: value)
    obj.connect("test-gvalue-ret", _gvalue_ret_callback)


def _gvalue_ret_callback(source: object, value_type: object) -> object:
    type_name = getattr(value_type, "gtype_name", None)
    if type_name == "gint" or value_type == 24:
        return 2**31 - 1
    if type_name == "guint" or value_type == 28:
        return 2**32 - 1
    if type_name == "gint64" or value_type == 40:
        return 2**63 - 1
    if type_name == "guint64" or value_type == 44:
        return 2**64 - 1
    if type_name == "gchararray" or value_type == 64:
        return "hello"
    return None
