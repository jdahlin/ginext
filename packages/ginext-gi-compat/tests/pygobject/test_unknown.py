import unittest

import pytest

from gi.repository import GObject

import testhelper


unknown_compat_xfail = pytest.mark.xfail(
    reason="unknown wrapper compatibility is incomplete",
    strict=False,
)


class TestUnknown(unittest.TestCase):
    @unknown_compat_xfail
    def test_unknown_interface(self):
        obj = testhelper.get_unknown()
        TestUnknownGType = GObject.GType.from_name("TestUnknown")
        TestUnknown = GObject.new(TestUnknownGType).__class__
        assert isinstance(obj, testhelper.Interface)
        assert isinstance(obj, TestUnknown)

    @unknown_compat_xfail
    def test_property(self):
        obj = testhelper.get_unknown()
        self.assertEqual(obj.get_property("some-property"), None)
        obj.set_property("some-property", "foo")

    @unknown_compat_xfail
    def test_unknown_property(self):
        obj = testhelper.get_unknown()
        self.assertRaises(TypeError, obj.get_property, "unknown")
        self.assertRaises(TypeError, obj.set_property, "unknown", "1")
