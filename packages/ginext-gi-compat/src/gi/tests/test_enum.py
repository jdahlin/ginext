import threading
import unittest
from typing import cast

import pytest

from gi.repository import Gio, GObject
from .helper import capture_glib_warnings


_lock = threading.Lock()
counter = 0


def get_id():
    global counter
    with _lock:
        counter += 1
        return counter


enum_declaration_xfail = pytest.mark.xfail(
    reason="PyGObject GEnum/GFlags declaration compatibility is incomplete",
    strict=False,
)


class EnumTests(unittest.TestCase):
    @enum_declaration_xfail
    def test_gtype(self):
        class MyEnum(GObject.GEnum):
            ONE = 1
            TWO = 2
            THREE = 3

        # The new enum has it's own GType, which subclasses GEnum
        self.assertIsInstance(MyEnum.__gtype__, GObject.GType)
        self.assertNotEqual(MyEnum.__gtype__, GObject.GEnum.__gtype__)
        self.assertEqual(MyEnum.__gtype__.parent, GObject.GEnum.__gtype__)
        self.assertTrue(MyEnum.__gtype__.is_a(GObject.GEnum.__gtype__))
        self.assertIn(MyEnum.__gtype__, GObject.GEnum.__gtype__.children)

        # The class can be looked up by name
        type_name = MyEnum.__gtype__.name
        self.assertIn("MyEnum", type_name)
        self.assertEqual(GObject.GType.from_name(type_name), MyEnum.__gtype__)

        # The Python class is registered as the wrapper for the GType
        self.assertIs(MyEnum.__gtype__.pytype, MyEnum)

    def test_values(self):
        class MyEnum(GObject.GEnum):
            ONE = 1
            FORTY_TWO = 42

        # As this is a stdlib enum, the enum values are subclasses of the enum
        self.assertIsInstance(MyEnum.ONE, MyEnum)
        self.assertIsInstance(MyEnum.FORTY_TWO, MyEnum)

        # We can see the registered enum values too:
        one = cast(GObject.GEnum, MyEnum.ONE)
        forty_two = cast(GObject.GEnum, MyEnum.FORTY_TWO)
        self.assertEqual(one.value_name, "ONE")
        self.assertEqual(one.value_nick, "one")
        self.assertEqual(forty_two.value_name, "FORTY_TWO")
        self.assertEqual(forty_two.value_nick, "forty-two")

    @enum_declaration_xfail
    def test_custom_type_name(self):
        type_name = f"MyEnum{get_id()}"

        class MyEnum(GObject.GEnum):
            __gtype_name__ = type_name
            ONE = 1

        self.assertEqual(MyEnum.__gtype__.name, type_name)

        # Trying to register a type with the same name fails:
        with (
            self.assertRaises(RuntimeError) as ex,
            capture_glib_warnings(allow_criticals=True) as w,
        ):

            class MyEnum2(GObject.GEnum):
                __gtype_name__ = type_name
                ONE = 1

        self.assertEqual(str(ex.exception), f"Unable to register enum '{type_name}'")
        self.assertEqual(len(w), 1)
        self.assertEqual(
            str(w[0].message), f"cannot register existing type '{type_name}'"
        )

    def test_enum_as_string(self):
        class ObjectWithEnum(GObject.GObject):
            socket_type = GObject.Property(
                type=Gio.SocketType,
                default=Gio.SocketType.DATAGRAM,
            )

        obj = ObjectWithEnum(socket_type="stream")

        assert obj.props.socket_type == Gio.SocketType.STREAM


class FlagsTests(unittest.TestCase):
    @enum_declaration_xfail
    def test_gtype(self):
        class MyFlags(GObject.GFlags):
            ONE = 1
            TWO = 2
            FOUR = 4

        # The new enum has it's own GType, which subclasses GFlags
        self.assertIsInstance(MyFlags.__gtype__, GObject.GType)
        self.assertNotEqual(MyFlags.__gtype__, GObject.GFlags.__gtype__)
        self.assertEqual(MyFlags.__gtype__.parent, GObject.GFlags.__gtype__)
        self.assertTrue(MyFlags.__gtype__.is_a(GObject.GFlags.__gtype__))
        self.assertIn(MyFlags.__gtype__, GObject.GFlags.__gtype__.children)

        # The class can be looked up by name
        type_name = MyFlags.__gtype__.name
        self.assertIn("MyFlags", type_name)
        self.assertEqual(GObject.GType.from_name(type_name), MyFlags.__gtype__)

        # The Python class is registered as the wrapper for the GType
        self.assertIs(MyFlags.__gtype__.pytype, MyFlags)

    def test_values(self):
        class MyFlags(GObject.GFlags):
            ONE = 1
            THIRTY_TWO = 32

        # As this is a stdlib enum, the enum values are subclasses of the enum
        self.assertIsInstance(MyFlags.ONE, MyFlags)
        self.assertIsInstance(MyFlags.THIRTY_TWO, MyFlags)

        # We can see the registered enum values too:
        one = cast(GObject.GFlags, MyFlags.ONE)
        thirty_two = cast(GObject.GFlags, MyFlags.THIRTY_TWO)
        self.assertEqual(one.value_names, ["ONE"])
        self.assertEqual(one.value_nicks, ["one"])
        self.assertEqual(thirty_two.value_names, ["THIRTY_TWO"])
        self.assertEqual(thirty_two.value_nicks, ["thirty-two"])

        # Similar for combinations of flags
        v = cast(GObject.GFlags, MyFlags.ONE | MyFlags.THIRTY_TWO)
        self.assertIsInstance(v, MyFlags)
        self.assertEqual(v.value_names, ["ONE", "THIRTY_TWO"])
        self.assertEqual(v.value_nicks, ["one", "thirty-two"])

    @enum_declaration_xfail
    def test_custom_type_name(self):
        type_name = f"MyFlags{get_id()}"

        class MyFlags(GObject.GFlags):
            __gtype_name__ = type_name
            ONE = 1

        self.assertEqual(MyFlags.__gtype__.name, type_name)

        # Trying to register a type with the same name fails:
        with (
            self.assertRaises(RuntimeError) as ex,
            capture_glib_warnings(allow_criticals=True) as w,
        ):

            class MyFlags2(GObject.GFlags):
                __gtype_name__ = type_name
                ONE = 1

        self.assertEqual(str(ex.exception), f"Unable to register flags '{type_name}'")
        self.assertEqual(len(w), 1)
        self.assertEqual(
            str(w[0].message), f"cannot register existing type '{type_name}'"
        )
