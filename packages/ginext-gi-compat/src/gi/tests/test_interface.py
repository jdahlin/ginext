import unittest
from typing import Any, cast

import pytest

from gi.repository import GObject
import testhelper


def create_my_unknown():
    GUnknown = cast(Any, GObject.type_from_name("TestUnknown"))
    Unknown = GUnknown.pytype

    class MyUnknown(Unknown, testhelper.Interface):
        some_property = GObject.Property(type=str)

        def __init__(self):
            Unknown.__init__(self)
            self.called = False

        def do_iface_method(self):
            self.called = True
            Unknown.do_iface_method(self)

    GObject.type_register(MyUnknown)
    return MyUnknown


def create_my_object():
    class MyObject(GObject.GObject, testhelper.Interface):
        some_property = GObject.Property(type=str)

        def __init__(self):
            GObject.GObject.__init__(self)
            self.called = False

        def do_iface_method(self):
            self.called = True

    GObject.type_register(MyObject)
    return MyObject


class TestIfaceImpl(unittest.TestCase):
    @pytest.mark.xfail(
        reason="unknown interface wrapper compatibility is incomplete",
        strict=False,
    )
    def test_reimplement_interface(self):
        MyUnknown = create_my_unknown()
        m = MyUnknown()
        m.iface_method()
        self.assertEqual(m.called, True)

    @pytest.mark.xfail(
        reason="interface implementation compatibility is incomplete",
        strict=False,
    )
    def test_implement_interface(self):
        MyObject = create_my_object()
        m = MyObject()
        m.iface_method()
        self.assertEqual(m.called, True)
