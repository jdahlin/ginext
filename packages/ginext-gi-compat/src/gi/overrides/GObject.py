from __future__ import annotations

from gi.repository import GObject as _GObject

__all__: list[str] = []

_ObjectClass = _GObject.ObjectClass
_raw_find_property = _ObjectClass.find_property


def _remove_from_method_infos(cls: type, name: str) -> None:
    try:
        from ginext.gobject.resolve import own_gimeta
        for owner in cls.__mro__:
            gimeta = own_gimeta(owner)
            if gimeta is None:
                continue
            gimeta.remove_method(name)
    except Exception:
        pass


def _coerce_to_cls(arg: object) -> type | None:
    """Convert a class, GType, or instance to a Python class with find_property."""
    if isinstance(arg, type) and hasattr(arg, "find_property"):
        return arg
    # GType-like object
    if hasattr(arg, "pytype"):
        cls = arg.pytype
        if cls is not None and hasattr(cls, "find_property"):
            return cls
    # GObject instance
    if hasattr(type(arg), "find_property"):
        return type(arg)
    return None


def _object_class_find_property(self_or_cls, *args, **kwargs):
    """Find a property on a class, GType, or instance."""
    cls = _coerce_to_cls(self_or_cls)
    if cls is None:
        raise TypeError(
            f"expected ObjectClass, a GObject class, GType, or instance; "
            f"got {type(self_or_cls).__name__}"
        )
    if len(args) == 1 and not kwargs:
        return cls.find_property(args[0])
    return cls.find_property(*args, **kwargs)


_ObjectClass.find_property = _object_class_find_property
_remove_from_method_infos(_ObjectClass, "find_property")
