import unittest
import ctypes
from ctypes import c_void_p, py_object, c_char_p

import pytest

import gi
from gi.repository import Gio


def get_capi():
    if not hasattr(ctypes, "pythonapi"):
        return None

    class CAPI(ctypes.Structure):
        _fields_ = [
            ("", c_void_p),
            ("", c_void_p),
            ("", c_void_p),
            ("newgobj", ctypes.PYFUNCTYPE(py_object, c_void_p)),
        ]

    api_obj = gi._gobject._PyGObject_API
    func_type = ctypes.PYFUNCTYPE(c_void_p, py_object, c_char_p)
    PyCapsule_GetPointer = func_type(("PyCapsule_GetPointer", ctypes.pythonapi))
    ptr = PyCapsule_GetPointer(api_obj, b"gobject._PyGObject_API")

    ptr = ctypes.cast(ptr, ctypes.POINTER(CAPI))
    return ptr.contents


class TestPythonCAPI(unittest.TestCase):
    @pytest.mark.xfail(
        reason="PyGObject private C API capsule is not exposed",
        strict=False,
    )
    def test_newgobj(self):
        capi = get_capi()
        if capi is None:
            self.skipTest("no pythonapi support")
        w = Gio.FileInfo()
        # XXX: ugh :/
        ptr = int(repr(w).split()[-1].split(")")[0], 16)

        new_w = capi.newgobj(ptr)
        assert w == new_w
