from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from ginext import Adw, Gdk, Gio, GLib, GObject, Gtk

from commander.components.location import display_file, expand_home
from commander.components.operations import (
    prompt_copy,
    prompt_create_folder,
    prompt_move,
    prompt_rename,
)
from commander.components.pane import CommanderPane
from commander.components.settings.settingsstore import STYLE_LEVELS
from commander.fs import File
from commander.providers import CommanderProviderContext, ProviderCapability

from .preferences import CommanderPreferencesDialog

if TYPE_CHECKING:
    from commander.app import CommanderApp

_COMPONENT_DIR = Path(__file__).resolve().parent
_COMPONENTS_DIR = _COMPONENT_DIR.parent
_WINDOW_UI = (_COMPONENT_DIR / "window.ui").read_text()
_MENUS_UI = str(_COMPONENT_DIR / "menus.ui")
_SHORTCUTS_UI = str(_COMPONENT_DIR / "shortcuts.ui")
_CSS_FILES = (
    _COMPONENT_DIR / "windowview.css",
    _COMPONENTS_DIR / "pane" / "paneview.css",
)
_QUICK_VIEW_ATTRIBUTES = ",".join(
    (
        "standard::name",
        "standard::display-name",
        "standard::type",
        "standard::size",
        "standard::icon",
        "standard::content-type",
    )
)
_LISTER_ATTRIBUTES = ",".join(
    (
        "standard::name",
        "standard::display-name",
        "standard::type",
        "standard::size",
        "standard::content-type",
    )
)


@Gtk.Template(string=_WINDOW_UI)
class CommanderWindow(Adw.ApplicationWindow, type_name="GoiCommanderWindow"):

    header_bar: Adw.HeaderBar
    toolbar_view: Adw.ToolbarView
    window_title: Adw.WindowTitle
    primary_menu_button: Gtk.MenuButton
    root_box: Gtk.Box = Gtk.Template.Child(name="root")
    panels_slot: Gtk.Box
    command_row: Gtk.Box
    function_row: Gtk.Box

    def __init__(self, application: CommanderApp) -> None:
        super().__init__(application=application)
        self.app = application
        self._preferences_dialog: CommanderPreferencesDialog | None = None
        self._help_overlay: Gtk.ShortcutsWindow | None = None

        self._load_css()
        self._install_actions()
        self._install_primary_menu()

        self.left = CommanderPane(
            "left",
            initial_location=self._saved_location("left"),
            show_hidden_files=self.app.settings.show_hidden_files,
            on_location_changed=self._on_pane_location_changed,
            on_focus_requested=self.focus_pane,
        )
        self.right = CommanderPane(
            "right",
            initial_location=self._saved_location("right"),
            show_hidden_files=self.app.settings.show_hidden_files,
            on_location_changed=self._on_pane_location_changed,
            on_focus_requested=self.focus_pane,
        )
        self.active_pane = self.left
        self._quick_view_source: CommanderPane | None = None
        self._quick_view_target: CommanderPane | None = None
        self.left_quick_view = self._build_quick_view_slot()
        self.right_quick_view = self._build_quick_view_slot()
        self.left_stack = self._build_panel_stack(self.left, self.left_quick_view)
        self.right_stack = self._build_panel_stack(self.right, self.right_quick_view)
        cast("GObject.Object", self.left.selection).connect(
            "notify::selected",
            lambda selection, pspec: self._on_selection_changed(
                selection, pspec, self.left
            ),
        )
        cast("GObject.Object", self.right.selection).connect(
            "notify::selected",
            lambda selection, pspec: self._on_selection_changed(
                selection, pspec, self.right
            ),
        )

        self.panels_slot.append(self._build_panels())
        self.command_row.append(self._build_command_line())
        self.function_row.append(self._build_function_bar())
        self._apply_style_level(self.app.settings.style_level)

        self.focus_pane(self.left, grab_focus=False)
        self._install_key_controller()

    def _saved_location(self, side: str) -> File:
        return File.from_uri(self.app.settings.location_uri(side))

    def _on_pane_location_changed(self, pane: CommanderPane, file_: File) -> None:
        self.app.settings.set_location_uri(pane.side, file_.uri)
        if pane is self.active_pane:
            self._refresh_prompt()

    def _load_css(self) -> None:
        provider = Gtk.CssProvider.new()
        provider.load_from_string("\n".join(path.read_text() for path in _CSS_FILES))
        display = Gdk.Display.get_default()
        assert display is not None
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _install_primary_menu(self) -> None:
        builder = Gtk.Builder.new_from_file(_MENUS_UI)
        menu_model = builder.get_object("primary_menu")
        assert isinstance(menu_model, Gio.MenuModel)
        self.primary_menu_button.set_menu_model(menu_model)

    def _apply_style_level(self, level: int) -> None:
        bounded = max(0, min(len(STYLE_LEVELS) - 1, level))
        for index in range(len(STYLE_LEVELS)):
            self.root_box.remove_css_class(f"style-level-{index}")
        self.root_box.add_css_class(f"style-level-{bounded}")
        self.window_title.set_subtitle(self._style_subtitle(bounded))

    def _style_subtitle(self, level: int) -> str:
        return f"{STYLE_LEVELS[level]} · {self._active_location_text()}"

    def _install_actions(self) -> None:
        actions: list[tuple[str, Callable[..., None], list[str]]] = [
            ("preferences", self._on_preferences, ["<Primary>comma"]),
            ("show-help-overlay", self._on_show_help_overlay, ["<Primary>question", "F1"]),
            ("about", self._on_about, []),
            ("activate-menu", self._on_activate_menu, ["F9", "F10"]),
            ("switch-pane", self._on_switch_pane, ["Tab"]),
            ("open", self._on_open, ["Return", "KP_Enter"]),
            (
                "enter-archive",
                self._on_enter_archive,
                [
                    "<Primary>Page_Down",
                    "<Primary>Return",
                    "<Primary>KP_Enter",
                ],
            ),
            ("parent", self._on_parent, ["BackSpace", "<Primary>Page_Up"]),
            ("home", self._on_home, ["<Primary>backslash", "<Primary>less"]),
            ("refresh", self._on_refresh, ["F2", "<Primary>r"]),
            ("view", self._on_view, ["F3"]),
            ("edit", self._on_placeholder_action, ["F4"]),
            ("copy", self._on_copy, ["F5"]),
            ("move", self._on_move, ["F6"]),
            ("mkdir", self._on_mkdir, ["F7"]),
            ("rename-local", self._on_rename_local, ["<Shift>F6"]),
            ("mkdir-target", self._on_mkdir_target, ["<Shift>F7"]),
            ("delete", self._on_placeholder_action, ["F8", "Delete"]),
            ("quick-view", self._on_quick_view, ["<Primary><Shift>q"]),
            ("quit", self._on_quit, ["<Primary>q", "<Alt>F4"]),
            ("swap-panels", self._on_swap_panels, ["<Primary>u"]),
            (
                "target-equals-source",
                self._on_target_equals_source,
                ["<Primary>i", "<Primary>equal"],
            ),
            ("sort-name", self._on_sort_name, ["<Primary>F3"]),
            ("sort-extension", self._on_sort_extension, ["<Primary>F4"]),
            ("sort-date", self._on_sort_date, ["<Primary>F5"]),
            ("sort-size", self._on_sort_size, ["<Primary>F6"]),
            ("show-all-files", self._on_show_all_files, ["<Primary>F10"]),
        ]

        placeholder_actions = (
            ("change-left-location", ["<Alt>F1"]),
            ("change-right-location", ["<Alt>F2"]),
            ("alternate-view", ["<Alt>F3"]),
            ("internal-view", ["<Alt><Shift>F3"]),
            ("pack", ["<Alt>F5"]),
            ("move-to-archive", ["<Alt><Shift>F5"]),
            ("unpack", ["<Alt>F6", "<Alt>F9"]),
            ("test-archives", ["<Alt><Shift>F9"]),
            ("find", ["<Alt>F7"]),
            ("find-separate", ["<Alt><Shift>F7"]),
            ("command-history", ["<Alt>F8"]),
            ("cd-tree", ["<Alt>F10"]),
            ("left-dir-bar", ["<Alt>F11"]),
            ("right-dir-bar", ["<Alt>F12"]),
            ("focus-toolbar", ["<Alt><Shift>F11"]),
            ("focus-vertical-toolbar", ["<Alt><Shift>F12"]),
            ("history-back", ["<Alt>Left"]),
            ("history-forward", ["<Alt>Right"]),
            ("history-list", ["<Alt>Down", "<Alt><Shift>Down"]),
            ("custom-columns-menu", ["<Shift>F1"]),
            ("compare-file-lists", ["<Shift>F2"]),
            ("view-current-file", ["<Shift>F3"]),
            ("new-text-file", ["<Shift>F4"]),
            ("copy-rename", ["<Shift>F5"]),
            ("copy-shortcuts", ["<Primary><Shift>F5"]),
            ("delete-direct", ["<Shift>F8", "<Shift>Delete"]),
            ("context-menu", ["<Shift>F10"]),
            ("minimize", ["<Shift>Escape"]),
            ("select-group", ["KP_Add"]),
            ("unselect-group", ["KP_Subtract"]),
            ("invert-selection", ["KP_Multiply"]),
            ("restore-selection", ["KP_Divide"]),
            ("select-all", ["<Primary>KP_Add"]),
            ("unselect-all", ["<Primary>KP_Subtract"]),
            ("select-same-extension", ["<Alt>KP_Add"]),
            ("unselect-same-extension", ["<Alt>KP_Subtract"]),
            ("comments-view", ["<Primary><Shift>F2"]),
            ("tree", ["<Primary>F8"]),
            ("separate-tree", ["<Primary><Shift>F8"]),
            ("print", ["<Primary>F9"]),
            ("programs-filter", ["<Primary>F11"]),
            ("custom-filter", ["<Primary>F12"]),
            ("select-command-line", ["<Primary>p"]),
            ("directory-branch", ["<Primary>b"]),
            ("directory-branch-selected", ["<Primary><Shift>b"]),
            ("directory-hotlist", ["<Primary>d"]),
            ("ftp-connect", ["<Primary>f"]),
            ("ftp-disconnect", ["<Primary><Shift>f"]),
            ("calculate-space", ["<Primary>l"]),
            ("multi-rename", ["<Primary>m"]),
            ("ftp-new", ["<Primary>n"]),
            ("quick-filter", ["<Primary>s"]),
            ("quick-filter-last", ["<Primary><Shift>s"]),
            ("new-tab", ["<Primary>t"]),
            ("new-tab-background", ["<Primary><Shift>t"]),
            ("swap-panels-tabs", ["<Primary><Shift>u"]),
            ("close-tab", ["<Primary>w"]),
            ("close-all-tabs", ["<Primary><Shift>w"]),
            ("edit-comment", ["<Primary>z"]),
        )
        actions.extend(
            (name, self._on_placeholder_action, accels) for name, accels in placeholder_actions
        )

        for name, callback, accels in actions:
            action = Gio.SimpleAction.new(name, None)
            action.activate.connect(callback)
            self.add_action(action)
            self.app.set_accels_for_action(f"win.{name}", list(accels))

    def _build_panels(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row.add_css_class("panels-row")
        row.append(self.left_stack)
        row.append(self._build_center_bar())
        row.append(self.right_stack)
        return row

    def _build_panel_stack(
        self,
        pane: CommanderPane,
        quick_view: Gtk.Widget,
    ) -> Gtk.Stack:
        stack = Gtk.Stack()
        stack.set_hexpand(True)
        stack.set_vexpand(True)
        stack.add_named(pane, "files")
        stack.add_named(quick_view, "quick-view")
        stack.set_visible_child_name("files")
        return stack

    def _build_quick_view_slot(self) -> Gtk.Box:
        slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        slot.add_css_class("quick-view")
        slot.set_hexpand(True)
        slot.set_vexpand(True)
        return slot

    def _build_center_bar(self) -> Gtk.Widget:
        bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bar.add_css_class("center-bar")
        for icon, action, tooltip in (
            ("system-search-symbolic", "win.view", "View"),
            ("document-edit-symbolic", "win.edit", "Edit"),
            ("edit-copy-symbolic", "win.copy", "Copy"),
            ("go-jump-symbolic", "win.move", "Move"),
            ("edit-delete-symbolic", "win.delete", "Delete"),
            ("folder-new-symbolic", "win.mkdir", "New folder"),
        ):
            button = Gtk.Button.new_from_icon_name(icon)
            button.set_action_name(action)
            button.set_tooltip_text(tooltip)
            button.add_css_class("center-button")
            bar.append(button)
        return bar

    def _build_command_line(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.add_css_class("command-line")
        self.prompt = Gtk.Label(label="~>", xalign=1.0)
        self.command_entry = Gtk.Entry()
        self.command_entry.set_has_frame(True)
        self.command_entry.set_hexpand(True)
        self.command_entry.activate.connect(self._on_command_activate)
        row.append(self.prompt)
        row.append(self.command_entry)
        self._refresh_prompt()
        return row

    def _build_function_bar(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.add_css_class("function-bar")
        for label, action in (
            ("F3 View", "win.view"),
            ("F4 Edit", "win.edit"),
            ("F5 Copy", "win.copy"),
            ("F6 Move", "win.move"),
            ("F7 NewFolder", "win.mkdir"),
            ("F8 Delete", "win.delete"),
            ("Quit", "win.quit"),
        ):
            button = Gtk.Button.new_with_label(label)
            button.set_action_name(action)
            button.add_css_class("function-button")
            row.append(button)
        return row

    def _install_key_controller(self) -> None:
        controller = Gtk.EventControllerKey.new()
        controller.key_pressed.connect(self._on_key_pressed)
        self.add_controller(controller)

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Tab:
            self.switch_pane()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if state & Gdk.ModifierType.CONTROL_MASK:
                self._on_enter_archive()
                return True
            if self.get_focus() is self.command_entry:
                return False
            self.focus_pane(self.active_pane, grab_focus=False)
            self.active_pane.activate_selected()
            return True
        if keyval == Gdk.KEY_BackSpace:
            self.focus_pane(self.active_pane, grab_focus=False)
            self.active_pane.go_parent()
            self._refresh_prompt()
            return True
        return False

    def focus_pane(self, pane: CommanderPane, *, grab_focus: bool = False) -> None:
        if pane is self.active_pane and pane.active:
            if grab_focus:
                pane.focus_file_view()
            return
        self.left.set_active(pane is self.left)
        self.right.set_active(pane is self.right)
        self.active_pane = pane
        if grab_focus:
            pane.focus_file_view()
        self._refresh_prompt()

    def switch_pane(self) -> None:
        target = self.right if self.active_pane is self.left else self.left
        if target is self._quick_view_target:
            self._hide_quick_view()
        self.focus_pane(target, grab_focus=True)

    def _on_switch_pane(self, *_args: object) -> None:
        self.switch_pane()

    def _on_open(self, *_args: object) -> None:
        self.focus_pane(self.active_pane, grab_focus=False)
        self.active_pane.activate_selected()
        self._refresh_prompt()

    def _on_enter_archive(self, *_args: object) -> None:
        self.focus_pane(self.active_pane, grab_focus=False)
        if self.active_pane.selected_is_parent_row():
            self.active_pane.go_parent()
            self._refresh_prompt()
            return
        self.active_pane.enter_selected_archive()
        self._refresh_prompt()

    def _on_parent(self, *_args: object) -> None:
        self.focus_pane(self.active_pane, grab_focus=False)
        self.active_pane.go_parent()
        self._refresh_prompt()

    def _on_home(self, *_args: object) -> None:
        self.focus_pane(self.active_pane, grab_focus=False)
        self.active_pane.go_home()
        self._refresh_prompt()

    def _on_refresh(self, *_args: object) -> None:
        self.focus_pane(self.active_pane, grab_focus=False)
        self.active_pane.refresh()

    def _on_swap_panels(self, *_args: object) -> None:
        left = self.left.current_dir
        right = self.right.current_dir
        self.left.set_location(right)
        self.right.set_location(left)
        self._refresh_prompt()

    def _on_target_equals_source(self, *_args: object) -> None:
        target = self.right if self.active_pane is self.left else self.left
        target.set_location(self.active_pane.current_dir)

    def _on_sort_name(self, *_args: object) -> None:
        self.active_pane.sort_by_name()

    def _on_sort_extension(self, *_args: object) -> None:
        self.active_pane.sort_by_extension()

    def _on_sort_date(self, *_args: object) -> None:
        self.active_pane.sort_by_date()

    def _on_sort_size(self, *_args: object) -> None:
        self.active_pane.sort_by_size()

    def _on_show_all_files(self, *_args: object) -> None:
        self.app.settings.set_show_hidden_files(True)
        self.left.set_show_hidden_files(True)
        self.right.set_show_hidden_files(True)

    def _on_preferences(self, *_args: object) -> None:
        if self._preferences_dialog is None:
            self._preferences_dialog = CommanderPreferencesDialog(
                self.app.settings,
                on_style_level_changed=self._apply_style_level,
            )
        self._preferences_dialog.present(self)

    def _on_show_help_overlay(self, *_args: object) -> None:
        if self._help_overlay is None:
            builder = Gtk.Builder.new_from_file(_SHORTCUTS_UI)
            help_overlay = builder.get_object("help_overlay")
            assert isinstance(help_overlay, Gtk.ShortcutsWindow)
            help_overlay.set_transient_for(self)
            self._help_overlay = help_overlay
        self._help_overlay.present()

    def _on_about(self, *_args: object) -> None:
        about = Adw.AboutDialog(
            application_name="Commander",
            application_icon="system-file-manager-symbolic",
            developer_name="ginext",
            version="0.0.0",
            comments="A dual-pane file manager showcase for ginext.",
            website="https://github.com/anthropics/goi",
            license_type=Gtk.License.MIT_X11,
        )
        about.present(self)

    def _on_activate_menu(self, *_args: object) -> None:
        self.primary_menu_button.activate()

    def _on_view(self, *_args: object) -> None:
        self.focus_pane(self.active_pane, grab_focus=False)
        if self.active_pane.selected_is_parent_row():
            self.active_pane.status.set_text("Lister cannot open parent row")
            return

        file_ = self.active_pane.selected_file()
        if file_ is None:
            self.active_pane.status.set_text("No file selected")
            return

        try:
            info = file_.query_info(_LISTER_ATTRIBUTES, Gio.FileQueryInfoFlags.NONE)
        except GLib.Error as error:
            self.active_pane.status.set_text(f"Lister inspect failed: {error}")
            return

        if info.get_file_type() == Gio.FileType.DIRECTORY:
            self.active_pane.status.set_text("Lister supports files, not directories")
            return

        from commander.components.lister import ListerWindow

        ListerWindow(self.app, file_, info).present()

    def _on_copy(self, *_args: object) -> None:
        source = self._selected_operation_file("Copy")
        if source is None:
            return
        target = self._opposite_pane(self.active_pane)
        prompt_copy(
            self,
            source=source,
            target_dir=target.current_dir,
            set_status=self.active_pane.status.set_text,
            on_success=lambda _result: target.refresh(),
        )

    def _on_move(self, *_args: object) -> None:
        source = self._selected_operation_file("Move")
        if source is None:
            return
        source_pane = self.active_pane
        target_pane = self._opposite_pane(source_pane)
        prompt_move(
            self,
            source=source,
            target_dir=target_pane.current_dir,
            set_status=source_pane.status.set_text,
            on_success=lambda _result: self._refresh_after_move(source_pane, target_pane),
        )

    def _on_mkdir(self, *_args: object) -> None:
        pane = self.active_pane
        prompt_create_folder(
            self,
            parent_dir=pane.current_dir,
            set_status=pane.status.set_text,
            on_success=lambda _result: pane.refresh(),
        )

    def _on_rename_local(self, *_args: object) -> None:
        source = self._selected_operation_file("Rename")
        if source is None:
            return
        pane = self.active_pane
        prompt_rename(
            self,
            source=source,
            set_status=pane.status.set_text,
            on_success=lambda _result: pane.refresh(),
        )

    def _on_mkdir_target(self, *_args: object) -> None:
        pane = self._opposite_pane(self.active_pane)
        prompt_create_folder(
            self,
            parent_dir=pane.current_dir,
            set_status=pane.status.set_text,
            on_success=lambda _result: pane.refresh(),
        )

    def _on_quick_view(self, *_args: object) -> None:
        source = self.active_pane
        target = self._opposite_pane(source)
        if self._quick_view_source is source and self._quick_view_target is target:
            self._hide_quick_view()
            return
        self._show_quick_view(source, target)

    def _on_selection_changed(
        self,
        _selection: object,
        _pspec: object,
        pane: CommanderPane,
    ) -> None:
        if pane is self._quick_view_source and self._quick_view_target is not None:
            self._show_quick_view(pane, self._quick_view_target)

    def _show_quick_view(self, source: CommanderPane, target: CommanderPane) -> None:
        slot = self._quick_view_slot_for(target)
        self._clear_quick_view(slot)

        viewer = self._quick_view_widget(source)
        slot.append(viewer)
        self._stack_for(target).set_visible_child_name("quick-view")
        self._quick_view_source = source
        self._quick_view_target = target
        self.focus_pane(source, grab_focus=False)

    def _hide_quick_view(self) -> None:
        if self._quick_view_target is not None:
            slot = self._quick_view_slot_for(self._quick_view_target)
            self._clear_quick_view(slot)
            self._stack_for(self._quick_view_target).set_visible_child_name("files")
        self._quick_view_source = None
        self._quick_view_target = None

    def _quick_view_widget(self, pane: CommanderPane) -> Gtk.Widget:
        file_ = pane.selected_file()
        info = pane.selected_info()
        if file_ is None or info is None or pane.selected_is_parent_row():
            return self._quick_view_message("No file selected")
        if info.get_file_type() == Gio.FileType.DIRECTORY:
            return self._quick_view_message("Directory selected")

        try:
            info = file_.query_info(_QUICK_VIEW_ATTRIBUTES, Gio.FileQueryInfoFlags.NONE)
        except GLib.Error as error:
            return self._quick_view_message(f"Unable to inspect file: {error}")

        provider = self.app.providers.best_for(
            ProviderCapability.QUICK_VIEW,
            file_,
            info,
            app=self.app,
            window=self,
        )
        if provider is None:
            content_type = info.get_content_type() or "unknown type"
            return self._quick_view_message(f"No provider for {content_type}")

        context = CommanderProviderContext(
            capability=ProviderCapability.QUICK_VIEW,
            app=self.app,
            window=self,
        )
        widget = provider.create_widget(file_, info, context)

        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        frame.add_css_class("quick-view-frame")
        frame.set_hexpand(True)
        frame.set_vexpand(True)
        header = Gtk.Label(label=f"{provider.label}: {info.get_display_name()}", xalign=0.0)
        header.add_css_class("quick-view-header")
        frame.append(header)
        frame.append(widget)
        return frame

    def _quick_view_message(self, message: str) -> Gtk.Widget:
        label = Gtk.Label(label=message, xalign=0.0, yalign=0.0)
        label.add_css_class("quick-view-message")
        label.set_wrap(True)
        label.set_hexpand(True)
        label.set_vexpand(True)
        return label

    def _clear_quick_view(self, slot: Gtk.Box) -> None:
        child = slot.get_first_child()
        while child is not None:
            slot.remove(child)
            child = slot.get_first_child()

    def _opposite_pane(self, pane: CommanderPane) -> CommanderPane:
        return self.right if pane is self.left else self.left

    def _stack_for(self, pane: CommanderPane) -> Gtk.Stack:
        return self.left_stack if pane is self.left else self.right_stack

    def _quick_view_slot_for(self, pane: CommanderPane) -> Gtk.Box:
        return self.left_quick_view if pane is self.left else self.right_quick_view

    def _on_placeholder_action(self, action: Gio.SimpleAction, *_args: object) -> None:
        name = action.get_name()
        self.command_entry.set_text(f"{name}: {self._active_location_text()}")
        self.command_entry.grab_focus()

    def _on_command_activate(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        if not text:
            return
        if text.startswith("cd "):
            target = expand_home(text[3:].strip())
            if "://" in target:
                self.active_pane.set_location(File.from_uri(target))
            else:
                self.active_pane.set_location(File.from_path(target))
            entry.set_text("")
            self._refresh_prompt()

    def _selected_operation_file(self, verb: str) -> File | None:
        if self.active_pane.selected_is_parent_row():
            self.active_pane.status.set_text(f"{verb} cannot use the parent row")
            return None
        file_ = self.active_pane.selected_file()
        if file_ is None:
            self.active_pane.status.set_text("No file selected")
            return None
        return file_

    def _refresh_after_move(self, source_pane: CommanderPane, target_pane: CommanderPane) -> None:
        source_pane.refresh()
        if target_pane is not source_pane:
            target_pane.refresh()

    def _on_quit(self, *_args: object) -> None:
        self.close()

    def _active_location_text(self) -> str:
        file_ = self.active_pane.selected_file() or self.active_pane.current_dir
        return display_file(file_)

    def _refresh_prompt(self) -> None:
        location = display_file(self.active_pane.current_dir)
        self.prompt.set_text(f"{location}>")
        self.window_title.set_subtitle(self._style_subtitle(self.app.settings.style_level))
