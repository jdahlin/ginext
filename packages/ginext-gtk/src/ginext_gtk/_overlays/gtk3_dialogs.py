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

"""GTK 3 only: Dialog, MessageDialog, and Button overlays."""

from __future__ import annotations

import warnings
from typing import cast

from ginext.gobject import gobjectclass as _gobject_root
from ginext import Gtk

overlay = Gtk.overlay


def _pygtk_deprecation_warning() -> type[DeprecationWarning]:
    return getattr(Gtk, "PyGTKDeprecationWarning", DeprecationWarning)


if Gtk.__version__[0] == 3:

    @overlay.method("Dialog", name="__init__")
    def _dialog_init(self: Gtk.Dialog, *args: object, **kwargs: object) -> None:
        if args:
            raise TypeError(
                "Gtk.Dialog() compat wrapper accepts keyword arguments only"
            )

        new_kwargs = dict(kwargs)
        add_buttons = None
        flags = new_kwargs.pop("flags", None)
        if flags is not None:
            if cast("int", flags) & Gtk.DialogFlags.MODAL:
                warnings.warn(
                    'Passing "flags" is deprecated; use "modal=True" instead',
                    _pygtk_deprecation_warning(),
                    stacklevel=2,
                )
                new_kwargs["modal"] = True
            if cast("int", flags) & Gtk.DialogFlags.DESTROY_WITH_PARENT:
                warnings.warn(
                    'Passing "flags" is deprecated; use "destroy_with_parent=True" instead',
                    _pygtk_deprecation_warning(),
                    stacklevel=2,
                )
                new_kwargs["destroy_with_parent"] = True

        buttons = new_kwargs.get("buttons")
        if buttons is not None and not isinstance(buttons, Gtk.ButtonsType):
            warnings.warn(
                'The "buttons" argument must be a Gtk.ButtonsType enum value. '
                'Please use the "add_buttons" method for adding buttons.',
                _pygtk_deprecation_warning(),
                stacklevel=2,
            )
            add_buttons = buttons
            new_kwargs.pop("buttons", None)

        _gobject_root.GObject.__init__(self, **new_kwargs)
        if add_buttons:
            self.add_buttons(*cast("tuple[object, ...]", add_buttons))

    @overlay.method("Dialog")
    def add_buttons(self: Gtk.Dialog, *args: object) -> None:
        if len(args) % 2:
            raise ValueError("Must pass an even number of arguments")
        for i in range(0, len(args), 2):
            self.add_button(cast("str", args[i]), cast("int", args[i + 1]))

    @overlay.property("Dialog")
    def action_area(self: Gtk.Dialog) -> Gtk.Box:
        return cast("Gtk.Box", self.get_action_area())

    @overlay.property("Dialog")
    def vbox(self: Gtk.Dialog) -> Gtk.Box:
        return self.get_content_area()

    @overlay.method("MessageDialog", name="__init__")
    def _message_dialog_init(
        self: Gtk.MessageDialog, *args: object, **kwargs: object
    ) -> None:
        if args:
            raise TypeError(
                "Gtk.MessageDialog() compat wrapper accepts keyword arguments only"
            )
        new_kwargs = dict(kwargs)
        if "text" in new_kwargs and "message_format" not in new_kwargs:
            new_kwargs["message_format"] = new_kwargs.pop("text")
        if "type" in new_kwargs and "message_type" not in new_kwargs:
            new_kwargs["message_type"] = new_kwargs.pop("type")
        flags = new_kwargs.pop("flags", None)
        if flags is not None:
            if cast("int", flags) & Gtk.DialogFlags.MODAL:
                warnings.warn(
                    'Passing "flags" is deprecated; use "modal=True" instead',
                    _pygtk_deprecation_warning(),
                    stacklevel=2,
                )
                new_kwargs["modal"] = True
            if cast("int", flags) & Gtk.DialogFlags.DESTROY_WITH_PARENT:
                warnings.warn(
                    'Passing "flags" is deprecated; use "destroy_with_parent=True" instead',
                    _pygtk_deprecation_warning(),
                    stacklevel=2,
                )
                new_kwargs["destroy_with_parent"] = True
        _gobject_root.GObject.__init__(self, **new_kwargs)

    @overlay.method("MessageDialog")
    def format_secondary_text(self: Gtk.MessageDialog, message_format: str) -> None:
        self.set_property_by_name("secondary-use-markup", False)
        self.set_property_by_name("secondary-text", message_format)

    @overlay.method("MessageDialog")
    def format_secondary_markup(self: Gtk.MessageDialog, message_format: str) -> None:
        self.set_property_by_name("secondary-use-markup", True)
        self.set_property_by_name("secondary-text", message_format)

    @overlay.method("Button", name="__init__")
    def _button_init(self: Gtk.Button, *args: object, **kwargs: object) -> None:
        stock = kwargs.get("stock")
        if stock:
            warnings.warn(
                "Stock items are deprecated. Please use: Gtk.Button.new_with_mnemonic(label)",
                _pygtk_deprecation_warning(),
                stacklevel=2,
            )
            new_kwargs = dict(kwargs)
            new_kwargs["label"] = new_kwargs.pop("stock")
            new_kwargs.setdefault("use_stock", True)
            new_kwargs.setdefault("use_underline", True)
            _gobject_root.GObject.__init__(self, **new_kwargs)
            return
        if args:
            raise TypeError(
                "Gtk.Button() compat wrapper accepts keyword arguments only"
            )
        _gobject_root.GObject.__init__(self, **kwargs)
