from __future__ import annotations

from ginext import Gtk

_TOOLBAR_ITEMS = (
    ("view-refresh", "win.refresh", "Refresh"),
    None,
    ("view-dual", "win.target-equals-source", "Target = Source"),
    ("document-open", "win.open", "Open"),
    ("image-x-generic", "win.view", "View image"),
    ("folder", "win.view", "Directory tree"),
    None,
    ("view-sort-ascending", "win.view", "Compare directories"),
    ("edit-select-all", "win.view", "Select files"),
    None,
    ("go-previous", "win.parent", "Back / parent"),
    ("go-next", "win.view", "Forward"),
    None,
    ("package-x-generic", "win.view", "Pack files"),
    ("folder-download", "win.view", "Unpack files"),
    None,
    ("network-server", "win.view", "FTP"),
    ("applications-internet", "win.view", "Open URL"),
    None,
    ("system-search", "win.view", "Search"),
    ("view-sort-ascending", "win.view", "Sort"),
    ("folder-sync", "win.view", "Synchronize"),
    ("folder-new", "win.mkdir", "New folder"),
    None,
    ("document-edit", "win.edit", "Edit"),
)


class CommanderToolbar(Gtk.Box, type_name="GoiCommanderToolbar"):

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("commander-toolbar")
        for item in _TOOLBAR_ITEMS:
            if item is None:
                self.append(_spacer())
                continue
            icon_name, action, tooltip = item
            self.append(_button(icon_name, action, tooltip))


def _button(icon_name: str, action: str, tooltip: str) -> Gtk.Button:
    image = Gtk.Image.new_from_icon_name(icon_name)
    image.set_pixel_size(18)
    button = Gtk.Button()
    button.add_css_class("toolbar-button")
    button.set_child(image)
    button.set_action_name(action)
    button.set_tooltip_text(tooltip)
    return button


def _spacer() -> Gtk.Box:
    spacer = Gtk.Box()
    spacer.add_css_class("toolbar-spacer")
    return spacer
