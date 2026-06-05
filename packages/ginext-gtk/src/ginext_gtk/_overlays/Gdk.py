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

import warnings
from typing import Iterator, NamedTuple, cast

from ginext import Gdk
from ginext import GLib as _GLib
from ginext import features
from ginext import private
from collections.abc import Callable


class _DownloadBytesResult(NamedTuple):
    data: _GLib.Bytes
    out_stride: int


class _DownloadBytesWithPlanesResult(NamedTuple):
    data: _GLib.Bytes
    out_stride: int
    out_offsets: list[int]


overlay = Gdk.overlay


@overlay.method("TextureDownloader", name="download_bytes")
def _td_download_bytes(
    fn: Callable[[Gdk.TextureDownloader], tuple[_GLib.Bytes, int]],
    self: Gdk.TextureDownloader,
) -> _DownloadBytesResult:
    return _DownloadBytesResult(*fn(self))


@overlay.method("TextureDownloader", name="download_bytes_with_planes")
def _td_download_bytes_with_planes(
    fn: Callable[[Gdk.TextureDownloader], tuple[_GLib.Bytes, int, list[int]]],
    self: Gdk.TextureDownloader,
) -> _DownloadBytesWithPlanesResult:
    return _DownloadBytesWithPlanesResult(*fn(self))


# ContentFormats: get_gtypes/get_mime_types already return plain lists at
# runtime (ginext coerces out-params). The GIR stub says tuple; the overlay
# method replaces it with the correct return type.
@overlay.method("ContentFormats", name="get_gtypes")
def _cf_get_gtypes(
    fn: Callable[[Gdk.ContentFormats], list[int]], self: Gdk.ContentFormats
) -> list[int]:
    return list(fn(self))


@overlay.method("ContentFormats", name="get_mime_types")
def _cf_get_mime_types(
    fn: Callable[[Gdk.ContentFormats], list[str]], self: Gdk.ContentFormats
) -> list[str]:
    return list(fn(self))


if Gdk.__version__[0] == 3:

    def _event_arm_name(event_type: object) -> str | None:
        key = int(cast("int", event_type))
        mapping = {
            int(Gdk.EventType.BUTTON_PRESS): "button",
            int(Gdk.EventType.BUTTON_RELEASE): "button",
            int(Gdk.EventType.CONFIGURE): "configure",  # type: ignore[attr-defined]  # Gdk3-only
            int(Gdk.EventType.DRAG_ENTER): "dnd",
            int(Gdk.EventType.DRAG_LEAVE): "dnd",
            int(Gdk.EventType.DRAG_MOTION): "dnd",
            int(Gdk.EventType.DROP_START): "dnd",
            int(Gdk.EventType.KEY_PRESS): "key",
            int(Gdk.EventType.KEY_RELEASE): "key",
            int(Gdk.EventType.MOTION_NOTIFY): "motion",
            int(Gdk.EventType.SCROLL): "scroll",
            int(Gdk.EventType.TOUCH_BEGIN): "touch",
            int(Gdk.EventType.TOUCH_CANCEL): "touch",
            int(Gdk.EventType.TOUCH_END): "touch",
            int(Gdk.EventType.TOUCH_UPDATE): "touch",
        }
        return mapping.get(key)

    def _event_active_arm(event: Gdk.Event) -> object:
        info = getattr(type(event), "gimeta").info
        event_type = private.record_field_get(event, info, "type")
        arm_name = _event_arm_name(event_type)
        if arm_name is None:
            raise AttributeError("event type has no active arm")
        return private.record_field_get(event, info, arm_name)

    class _EventArmField:
        __slots__ = ("_name",)

        def __init__(self, name: str) -> None:
            self._name = name

        def __get__(self, event: Gdk.Event | None, owner: type | None = None) -> object:
            if event is None:
                return self
            arm = _event_active_arm(event)
            return private.record_field_get(arm, getattr(type(arm), "gimeta").info, self._name)

        def __set__(self, event: Gdk.Event, value: object) -> None:
            arm = _event_active_arm(event)
            private.record_field_set(arm, getattr(type(arm), "gimeta").info, self._name, value)

    class _EventMixin:
        direction = _EventArmField("direction")
        emulating_pointer = _EventArmField("emulating_pointer")
        state = _EventArmField("state")
        x = _EventArmField("x")
        x_root = _EventArmField("x_root")
        y = _EventArmField("y")
        y_root = _EventArmField("y_root")

    overlay.bases("Event", (_EventMixin,))

    overlay.constant("SELECTION_CLIPBOARD", Gdk.atom_intern("CLIPBOARD", True))
    overlay.constant("SELECTION_PRIMARY", Gdk.atom_intern("PRIMARY", True))


@overlay.method("RGBA", name="__new__", as_staticmethod=True)
def _rgba_new(
    cls: type[Gdk.RGBA],
    red: float = 0.0,
    green: float = 0.0,
    blue: float = 0.0,
    alpha: float = 1.0,
) -> Gdk.RGBA:
    # Mirror RecordBase.__new__'s compat deprecation: this custom constructor
    # bypasses it. The shared message is matched by the pyproject filterwarnings.
    if features.is_enabled(features.PYGOBJECT_COMPAT):
        warnings.warn(
            f"{cls.__name__} positional/keyword construction is deprecated",
            DeprecationWarning,
            stacklevel=2,
        )
    info = getattr(cls, "gimeta").info
    obj = private.record_new(cls, info)
    private.record_field_set(obj, info, "red", float(red))
    private.record_field_set(obj, info, "green", float(green))
    private.record_field_set(obj, info, "blue", float(blue))
    private.record_field_set(obj, info, "alpha", float(alpha))
    return cast("Gdk.RGBA", obj)


@overlay.method("RGBA", name="__repr__")
def _rgba_repr(self: Gdk.RGBA) -> str:
    return f"Gdk.RGBA({self.to_string()!r})"


@overlay.method("Rectangle", name="__new__", as_staticmethod=True)
def _rectangle_new(
    cls: type[Gdk.Rectangle],
    x: int = 0,
    y: int = 0,
    width: int = 0,
    height: int = 0,
) -> Gdk.Rectangle:
    info = getattr(cls, "gimeta").info
    obj = private.record_new(cls, info)
    private.record_field_set(obj, info, "x", int(x))
    private.record_field_set(obj, info, "y", int(y))
    private.record_field_set(obj, info, "width", int(width))
    private.record_field_set(obj, info, "height", int(height))
    return cast("Gdk.Rectangle", obj)


@overlay.method("Rectangle", name="__repr__")
def _rectangle_repr(self: Gdk.Rectangle) -> str:
    return (
        f"Gdk.Rectangle(x={self.x}, y={self.y}, "
        f"width={self.width}, height={self.height})"
    )


@overlay.method("ContentFormats", name="__len__")
def _content_formats_len(self: Gdk.ContentFormats) -> int:
    return len(self.get_mime_types())


@overlay.method("ContentFormats", name="__iter__")
def _content_formats_iter(self: Gdk.ContentFormats) -> Iterator[str]:
    yield from self.get_mime_types()


@overlay.method("ContentFormats", name="__contains__")
def _content_formats_contains(self: Gdk.ContentFormats, value: str) -> bool:
    return bool(self.contain_mime_type(value))


@overlay.method("ContentFormats", name="__repr__")
def _content_formats_repr(self: Gdk.ContentFormats) -> str:
    return f"Gdk.ContentFormats({self.get_mime_types()!r})"


# Gtk-4 has no Gdk.Atom; the registration is dormant when Gdk-4.0 loads.
@overlay.method("Atom", name="__repr__")
def _atom_repr(self: Gdk.Atom) -> str:
    return f'Gdk.Atom.intern("{self.name()}", False)'
