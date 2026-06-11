from __future__ import annotations

from gi.repository import Gdk as _Gdk

__all__: list[str] = []

_RGBA = _Gdk.RGBA


def _rgba_repr(self) -> str:
    return (
        f"Gdk.RGBA(red={self.red!r}, green={self.green!r}, "
        f"blue={self.blue!r}, alpha={self.alpha!r})"
    )


def _rgba_iter(self):
    yield self.red
    yield self.green
    yield self.blue
    yield self.alpha


def _rgba_eq(self, other) -> bool:
    if not isinstance(other, _RGBA):
        return NotImplemented
    return (
        self.red == other.red
        and self.green == other.green
        and self.blue == other.blue
        and self.alpha == other.alpha
    )


def _rgba_ne(self, other) -> bool:
    result = _rgba_eq(self, other)
    if result is NotImplemented:
        return result
    return not result


def _rgba_hash(self) -> int:
    return hash((self.red, self.green, self.blue, self.alpha))


def _remove_from_method_infos(cls: type, name: str) -> None:
    try:
        from ginext.gobject.resolve import own_gimeta
        for owner in cls.__mro__:
            gimeta = own_gimeta(owner)
            if gimeta is None:
                continue
            method_infos = getattr(gimeta, "method_infos", {})
            if name in method_infos:
                del method_infos[name]
    except Exception:
        pass


_RGBA.__repr__ = _rgba_repr
_RGBA.__iter__ = _rgba_iter
_RGBA.__eq__ = _rgba_eq
_RGBA.__ne__ = _rgba_ne
_RGBA.__hash__ = _rgba_hash
for _name in ("__repr__", "__iter__", "__eq__", "__ne__", "__hash__"):
    _remove_from_method_infos(_RGBA, _name)

RGBA = _RGBA
__all__.append("RGBA")

# FileList: add __len__ and __getitem__ using get_files()
_FileList = getattr(_Gdk, "FileList", None)
if _FileList is not None:
    def _filelist_len(self) -> int:
        return len(self.get_files())

    def _filelist_getitem(self, index: int) -> object:
        return self.get_files()[index]

    _FileList.__len__ = _filelist_len  # type: ignore[attr-defined]
    _FileList.__getitem__ = _filelist_getitem  # type: ignore[attr-defined]
    for _name in ("__len__", "__getitem__"):
        _remove_from_method_infos(_FileList, _name)

    FileList = _FileList
    __all__.append("FileList")
    del _name


# PaintableFlags aliases: SIZE -> STATIC_SIZE, CONTENTS -> STATIC_CONTENTS
try:
    _PaintableFlags = _Gdk.PaintableFlags
    if not hasattr(_PaintableFlags, "SIZE") and hasattr(_PaintableFlags, "STATIC_SIZE"):
        _PaintableFlags.SIZE = _PaintableFlags.STATIC_SIZE
    if not hasattr(_PaintableFlags, "CONTENTS") and hasattr(_PaintableFlags, "STATIC_CONTENTS"):
        _PaintableFlags.CONTENTS = _PaintableFlags.STATIC_CONTENTS
except AttributeError:
    pass
