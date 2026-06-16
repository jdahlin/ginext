from __future__ import annotations

from typing import Any

from gi.repository import Gtk


class PyGTKDeprecationWarning(DeprecationWarning):
    pass


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


_Builder = Gtk.Builder

_raw_builder_add_from_string = _Builder.add_from_string
_raw_builder_add_objects_from_string = _Builder.add_objects_from_string


_raw_builder_init = _Builder.__init__


def _builder_init(self, connect_func=None, **kwargs):
    _raw_builder_init(self, **kwargs)
    # Store connect function for GTK4-style signal connection
    if connect_func is not None:
        object.__setattr__(self, "_compat_connect_func", connect_func)


def _builder_add_from_string(self, buffer, length=-1):
    if not isinstance(buffer, str):
        raise TypeError("buffer must be a string")
    if length == -1:
        length = len(buffer.encode("utf-8"))
    return _raw_builder_add_from_string(self, buffer, length)


def _builder_add_objects_from_string(self, buffer, object_ids, length=-1):
    if not isinstance(buffer, str):
        raise TypeError("buffer must be a string")
    if length == -1:
        length = len(buffer.encode("utf-8"))
    return _raw_builder_add_objects_from_string(self, buffer, length, object_ids)


_Builder.__init__ = _builder_init
_Builder.add_from_string = _builder_add_from_string
_Builder.add_objects_from_string = _builder_add_objects_from_string
for _name in ("__init__", "add_from_string", "add_objects_from_string"):
    _remove_from_method_infos(_Builder, _name)

_Editable = Gtk.Editable
if _Editable is not None:
    _raw_editable_insert_text = _Editable.insert_text

    def _editable_insert_text(self, text, position):
        return _raw_editable_insert_text(self, text, len(text.encode("utf-8")), position)

    _Editable.insert_text = _editable_insert_text
    _remove_from_method_infos(_Editable, "insert_text")

_Widget = Gtk.Widget
if _Widget is not None:
    _raw_translate_coordinates = _Widget.translate_coordinates

    def _translate_coordinates(self, dest_widget, src_x, src_y):
        result = _raw_translate_coordinates(self, dest_widget, src_x, src_y)
        # ginext returns a ResultTuple: (ret_bool, dest_x, dest_y)
        try:
            ret = result[0]
        except (TypeError, IndexError):
            return result
        if not ret:
            return None
        return (result[1], result[2])

    _Widget.translate_coordinates = _translate_coordinates
    _remove_from_method_infos(_Widget, "translate_coordinates")

_Window = getattr(Gtk, "Window", None)
if _Window is not None:
    _raw_get_default_size = _Window.get_default_size

    def _get_default_size(self):
        result = _raw_get_default_size(self)
        # ginext returns a SimpleNamespace with .width and .height
        if hasattr(result, "width") and hasattr(result, "height"):
            return (result.width, result.height)
        return result

    _Window.get_default_size = _get_default_size
    _remove_from_method_infos(_Window, "get_default_size")

_Dialog = Gtk.Dialog
if _Dialog is not None:
    def _dialog_add_buttons(self, *args):
        if len(args) % 2 != 0:
            raise ValueError("add_buttons requires an even number of arguments")
        for label, response_id in zip(args[::2], args[1::2]):
            self.add_button(label, response_id)

    _Dialog.add_buttons = _dialog_add_buttons
    _remove_from_method_infos(_Dialog, "add_buttons")

Action: Any = getattr(Gtk, "Action", None)
ActionGroup: Any = getattr(Gtk, "ActionGroup", None)
Builder = _Builder
Button = Gtk.Button
Dialog = _Dialog
Editable = _Editable
ListStore = Gtk.ListStore
MessageDialog = Gtk.MessageDialog
RadioAction: Any = getattr(Gtk, "RadioAction", None)
TextBuffer = Gtk.TextBuffer
TextIter = Gtk.TextIter
TreeModel = Gtk.TreeModel
TreeModelSort = Gtk.TreeModelSort
TreeStore = Gtk.TreeStore
TreeViewColumn = Gtk.TreeViewColumn
UIManager: Any = getattr(Gtk, "UIManager", None)

if getattr(Gtk, "_version", "") != "4.0":
    ColorSelectionDialog: Any = getattr(Gtk, "ColorSelectionDialog", None)
    FileChooserDialog = Gtk.FileChooserDialog
    FontSelectionDialog: Any = getattr(Gtk, "FontSelectionDialog", None)
    RecentChooserDialog: Any = getattr(Gtk, "RecentChooserDialog", None)

__all__ = [
    "PyGTKDeprecationWarning",
    "Action",
    "ActionGroup",
    "Builder",
    "Button",
    "Dialog",
    "Editable",
    "ListStore",
    "MessageDialog",
    "RadioAction",
    "TextBuffer",
    "TextIter",
    "TreeModel",
    "TreeModelSort",
    "TreeStore",
    "TreeViewColumn",
    "UIManager",
]

if getattr(Gtk, "_version", "") != "4.0":
    __all__.extend(
        [
            "ColorSelectionDialog",
            "FileChooserDialog",
            "FontSelectionDialog",
            "RecentChooserDialog",
        ]
    )
