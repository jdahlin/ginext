# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

import warnings
from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING, NamedTuple, TypeVar, cast

from ginext import Pango
from ginext import features

if TYPE_CHECKING:
    from ginext.overlay.registrar import OverlayRegistrar

    TabArray = object
    TabAlign = object
    AttrList = object
    Attribute = object
    FontDescription = object
    Language = object
    Context = object
    Script = object


class ScriptIterRange(NamedTuple):
    start: str
    end: str
    script: object


class LayoutPixelSize(NamedTuple):
    width: int
    height: int


class XyToIndex(NamedTuple):
    inside: bool
    index_: int
    trailing: int


class IndexToLineX(NamedTuple):
    line: int
    x_pos: int


class MoveCursorVisually(NamedTuple):
    new_index: int
    new_trailing: int


ResultTuple = TypeVar("ResultTuple")


overlay: OverlayRegistrar = Pango.overlay


def _named_result(
    result_type: type[ResultTuple],
    value: object,
) -> ResultTuple:
    field_names = getattr(result_type, "_fields", None)
    if not isinstance(field_names, tuple):
        raise TypeError(f"{result_type!r} is not a NamedTuple type")
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return result_type(*value)
    return result_type(*(getattr(value, name) for name in field_names))


@overlay.method("TabArray", name="__len__")
def _tab_array_len(self: TabArray) -> int:
    return int(self.get_size())


@overlay.method("TabArray", name="__getitem__")
def _tab_array_getitem(self: TabArray, index: int) -> tuple[TabAlign, int]:
    size = _tab_array_len(self)
    if index < 0:
        index += size
    if index < 0 or index >= size:
        raise IndexError(index)
    align, location = self.get_tab(index)
    return align, int(location)


@overlay.method("TabArray", name="__iter__")
def _tab_array_iter(self: TabArray) -> Iterator[tuple[TabAlign, int]]:
    for index in range(_tab_array_len(self)):
        yield _tab_array_getitem(self, index)


@overlay.method("TabArray", name="__repr__")
def _tab_array_repr(self: TabArray) -> str:
    return f"Pango.TabArray({list(_tab_array_iter(self))!r}, pixels={self.get_positions_in_pixels()!r})"


@overlay.method("AttrList", name="__len__")
def _attr_list_len(self: AttrList) -> int:
    return len(self.get_attributes())


@overlay.method("AttrList", name="__iter__")
def _attr_list_iter(self: AttrList) -> Iterator[Attribute]:
    yield from self.get_attributes()


@overlay.method("AttrList", name="__repr__")
def _attr_list_repr(self: AttrList) -> str:
    return f"Pango.AttrList({self.to_string()!r})"


@overlay.method("FontDescription", name="__new__", as_staticmethod=True)
def _font_description_new(
    cls: type[FontDescription],
    string: str | None = None,
) -> FontDescription:
    # PyGObject parses a positional string as a font description (via
    # font_description_from_string); the generic RecordBase.__new__ would
    # instead drop the argument and yield an empty description, which then
    # crashes pango_context_get_metrics on the macOS CoreText backend.
    #
    # PangoFontDescription is an opaque boxed type (no introspected size), so it
    # must be built by its constructor; allocating it as a bare record yields an
    # undersized struct whose fields read out of bounds.
    if string is None:
        return cast("FontDescription", cls.new())
    # Mirror RecordBase.__new__'s compat deprecation; the shared message is
    # matched by the pyproject filterwarnings.
    if features.is_enabled(features.PYGOBJECT_COMPAT):
        warnings.warn(
            f"{cls.__name__} positional/keyword construction is deprecated",
            DeprecationWarning,
            stacklevel=2,
        )
    return cast("FontDescription", cls.from_string(string))


@overlay.method("FontDescription", name="__str__")
def _font_description_str(self: FontDescription) -> str:
    return str(self.to_string())


@overlay.method("FontDescription", name="__repr__")
def _font_description_repr(self: FontDescription) -> str:
    return f"Pango.FontDescription({self.to_string()!r})"


@overlay.method("Language", name="__str__")
def _language_str(self: Language) -> str:
    return str(self.to_string())


@overlay.method("Language", name="__repr__")
def _language_repr(self: Language) -> str:
    return f"Pango.Language({self.to_string()!r})"


@overlay.method("Context")
def load_fontset(
    fn: Callable[..., object], self: Context, *args: object, **kwargs: object
) -> object:
    fontset = fn(self, *args, **kwargs)
    if fontset is not None:
        fontset._ginext_keepalive_context = self
    return fontset


# NamedReturn wrappers: methods that return ResultTuples with named fields.
# The overlay replaces the GIR method so the harvester emits the NamedTuple
# return type, giving test code access to .start/.end/.index_/etc.


@overlay.method("ScriptIter", name="get_range")
def _script_iter_get_range(
    fn: Callable[[object], object], self: object
) -> ScriptIterRange:
    return _named_result(ScriptIterRange, fn(self))


@overlay.method("Layout", name="get_pixel_size")
def _layout_get_pixel_size(
    fn: Callable[[object], object], self: object
) -> LayoutPixelSize:
    return _named_result(LayoutPixelSize, fn(self))


@overlay.method("Layout", name="get_size")
def _layout_get_size(fn: Callable[[object], object], self: object) -> LayoutPixelSize:
    return _named_result(LayoutPixelSize, fn(self))


@overlay.method("Layout", name="xy_to_index")
def _layout_xy_to_index(
    fn: Callable[[object, int, int], object], self: object, x: int, y: int
) -> XyToIndex:
    return _named_result(XyToIndex, fn(self, x, y))


@overlay.method("Layout", name="index_to_line_x")
def _layout_index_to_line_x(
    fn: Callable[[object, int, bool], object], self: object, index: int, trailing: bool
) -> IndexToLineX:
    return _named_result(IndexToLineX, fn(self, index, trailing))


@overlay.method("Layout", name="move_cursor_visually")
def _layout_move_cursor_visually(
    fn: Callable[[object, bool, int, int, int], object],
    self: object,
    strong: bool,
    old_index: int,
    old_trailing: int,
    direction: int,
) -> MoveCursorVisually:
    return _named_result(
        MoveCursorVisually,
        fn(self, strong, old_index, old_trailing, direction),
    )
