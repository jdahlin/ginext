from __future__ import annotations

from gi.repository import GIMarshallingTests as _GIMarshallingTests

__all__: list[str] = []

OVERRIDES_CONSTANT = 7
__all__.append("OVERRIDES_CONSTANT")


def _remove_from_method_infos(cls: type, name: str) -> None:
    """Remove a method from ginext's lazy-install list so our patch isn't overwritten."""
    try:
        from ginext.gobject.resolve import own_gimeta
        for owner in cls.__mro__:
            gimeta = own_gimeta(owner)
            if gimeta is None:
                continue
            gimeta.remove_method(name)
    except Exception:
        pass


# Patch OverridesStruct.method to return value/7 as the override does.
_orig_struct_method = _GIMarshallingTests.OverridesStruct.method


def _struct_method(self):
    return _orig_struct_method(self) / 7


_GIMarshallingTests.OverridesStruct.method = _struct_method
_remove_from_method_infos(_GIMarshallingTests.OverridesStruct, "method")
_GIMarshallingTests.OverridesStruct.__module__ = "gi.overrides.GIMarshallingTests"

OverridesStruct = _GIMarshallingTests.OverridesStruct
__all__.append("OverridesStruct")

_orig_obj_method = _GIMarshallingTests.OverridesObject.method


def _obj_method(self):
    """Overridden doc string."""
    return _orig_obj_method(self) / 7


_orig_obj_init = _GIMarshallingTests.OverridesObject.__init__
_orig_obj_new = _GIMarshallingTests.OverridesObject.new


def _obj_init(self, long_=None):
    _orig_obj_init(self)


def _obj_new(long_=None):
    return _orig_obj_new()


_GIMarshallingTests.OverridesObject.method = _obj_method
_GIMarshallingTests.OverridesObject.__init__ = _obj_init
_GIMarshallingTests.OverridesObject.new = staticmethod(_obj_new)
_remove_from_method_infos(_GIMarshallingTests.OverridesObject, "method")
_GIMarshallingTests.OverridesObject.__module__ = "gi.overrides.GIMarshallingTests"

OverridesObject = _GIMarshallingTests.OverridesObject
__all__.append("OverridesObject")
