from __future__ import annotations

from typing import Any

from gi.repository import Gtk


class PyGTKDeprecationWarning(DeprecationWarning):
    pass

Action: Any = getattr(Gtk, "Action", None)
ActionGroup: Any = getattr(Gtk, "ActionGroup", None)
Builder = Gtk.Builder
Button = Gtk.Button
Dialog = Gtk.Dialog
Editable = Gtk.Editable
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
