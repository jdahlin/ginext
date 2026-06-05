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

"""GTK 3 only: Builder overlays."""

from __future__ import annotations

from ginext import GObject, Gtk

overlay = Gtk.overlay

if Gtk.__version__[0] == 3:

    def _builder_connect_callback(
        builder: Gtk.Builder,
        gobj: GObject.Object,
        signal_name: str,
        handler_name: str,
        connect_obj: GObject.Object | None,
        flags: int,
        obj_or_map: object,
    ) -> None:
        from gi import _gtktemplate

        handler, extra_args = _gtktemplate._extract_handler_and_args(
            obj_or_map, handler_name
        )
        after = bool(flags & GObject.ConnectFlags.AFTER)
        if connect_obj is not None:
            if after:
                gobj.connect_object_after(
                    signal_name, handler, connect_obj, *extra_args
                )
            else:
                gobj.connect_object(signal_name, handler, connect_obj, *extra_args)
            return
        if after:
            gobj.connect_after(signal_name, handler, *extra_args)
        else:
            gobj.connect(signal_name, handler, *extra_args)

    @overlay.method("Builder")
    def connect_signals(self: Gtk.Builder, obj_or_map: object) -> None:
        self.connect_signals_full(_builder_connect_callback, obj_or_map)

    @overlay.method("Builder")
    def add_from_string(self: Gtk.Builder, buffer: str) -> bool:
        if not isinstance(buffer, str):
            raise TypeError("buffer must be a string")
        return Gtk.Builder.add_from_string(self, buffer, len(buffer.encode("utf-8")))

    @overlay.method("Builder")
    def add_objects_from_string(
        self: Gtk.Builder, buffer: str, object_ids: list[str]
    ) -> bool:
        if not isinstance(buffer, str):
            raise TypeError("buffer must be a string")
        return Gtk.Builder.add_objects_from_string(
            self,
            buffer,
            len(buffer.encode("utf-8")),
            object_ids,
        )
