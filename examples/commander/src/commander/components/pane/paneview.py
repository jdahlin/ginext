from __future__ import annotations

import gzip
import locale
import tempfile
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import cast

from ginext import Gio, GLib, GObject, Gtk, Pango

_GZIP_ERRORS = (GLib.Error, OSError, EOFError, gzip.BadGzipFile, zlib.error)
from ginext.gobject.gtype import GType

from commander.components.archive import (
    archive_file_for_root,
    enter_archive,
    extract_gzip_member,
    gzip_member_name,
    is_plain_gzip,
)
from commander.components.location import (
    LocationChoice,
    choose_location_index,
    display_file,
    expand_home,
    list_location_choices,
)
from commander.fs import File

FILE_ATTRIBUTES = ",".join(
    (
        "standard::name",
        "standard::display-name",
        "standard::type",
        "standard::size",
        "standard::icon",
        "standard::content-type",
        "standard::is-hidden",
        "time::modified",
        "unix::mode",
    )
)

FS_ATTRIBUTES = ",".join(
    (
        "filesystem::free",
        "filesystem::size",
    )
)

PARENT_ROW_NAME = ".."
DATETIME_FORMAT = "%x %X"


def _file_type_is_directory(info: Gio.FileInfo) -> bool:
    return info.get_file_type() == Gio.FileType.DIRECTORY


def _is_parent_row(info: Gio.FileInfo) -> bool:
    return info.get_name() == PARENT_ROW_NAME and bool(
        info.get_attribute_boolean("commander::parent-row")
    )


def _make_parent_info() -> Gio.FileInfo:
    info = Gio.FileInfo.new()
    info.set_name(PARENT_ROW_NAME)
    info.set_display_name(PARENT_ROW_NAME)
    info.set_file_type(Gio.FileType.DIRECTORY)
    info.set_size(0)
    info.set_icon(Gio.ThemedIcon.new("go-up-symbolic"))
    info.set_is_hidden(False)
    info.set_attribute_boolean("commander::parent-row", True)
    return info


def _format_size(info: Gio.FileInfo) -> str:
    if _file_type_is_directory(info):
        return "<DIR>"
    return _format_human_size(info.get_size())


def _format_mtime(info: Gio.FileInfo) -> str:
    dt = info.get_modification_date_time()
    if dt is None:
        return ""
    return dt.format(DATETIME_FORMAT) or ""


def _format_attr(info: Gio.FileInfo) -> str:
    attrs = ["-", "-", "-", "-"]
    if info.has_attribute("unix::mode"):
        mode = info.get_attribute_uint32("unix::mode")
        if mode:
            attrs[0] = "r" if mode & 0o400 else "-"
            attrs[1] = "w" if mode & 0o200 else "-"
            attrs[2] = "x" if mode & 0o100 else "-"
    if info.has_attribute("standard::is-hidden"):
        if info.get_is_hidden():
            attrs[3] = "h"
    return "".join(attrs)


def _split_name(info: Gio.FileInfo) -> tuple[str, str]:
    name = info.get_display_name() or info.get_name() or ""
    if _file_type_is_directory(info):
        return f"[{name}]", ""
    stem, dot, ext = name.rpartition(".")
    if dot and stem:
        return stem, ext
    return name, ""


def _format_bytes(value: int) -> str:
    return f"{_format_number(value)} k" if value else "?"


def _format_human_size(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    size = float(value)
    unit_index = 0
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{_format_number(value)} {units[unit_index]}"
    if size >= 10.0:
        return f"{locale.format_string('%.0f', size, grouping=True)} {units[unit_index]}"
    return f"{locale.format_string('%.1f', size, grouping=True)} {units[unit_index]}"


def _format_number(value: int) -> str:
    return locale.format_string("%d", value, grouping=True)


def _text_compare(left: str, right: str) -> Gtk.Ordering:
    left_folded = left.casefold()
    right_folded = right.casefold()
    if left_folded < right_folded:
        return Gtk.Ordering.SMALLER
    if left_folded > right_folded:
        return Gtk.Ordering.LARGER
    return Gtk.Ordering.EQUAL


def _number_compare(left: int, right: int) -> Gtk.Ordering:
    if left < right:
        return Gtk.Ordering.SMALLER
    if left > right:
        return Gtk.Ordering.LARGER
    return Gtk.Ordering.EQUAL


def _dir_first_compare(left: Gio.FileInfo, right: Gio.FileInfo) -> Gtk.Ordering:
    left_is_parent = _is_parent_row(left)
    right_is_parent = _is_parent_row(right)
    if left_is_parent and not right_is_parent:
        return Gtk.Ordering.SMALLER
    if right_is_parent and not left_is_parent:
        return Gtk.Ordering.LARGER

    left_is_dir = _file_type_is_directory(left)
    right_is_dir = _file_type_is_directory(right)
    if left_is_dir and not right_is_dir:
        return Gtk.Ordering.SMALLER
    if right_is_dir and not left_is_dir:
        return Gtk.Ordering.LARGER
    return Gtk.Ordering.EQUAL


def _chain_compare(*comparisons: Gtk.Ordering) -> Gtk.Ordering:
    for result in comparisons:
        if result != Gtk.Ordering.EQUAL:
            return result
    return Gtk.Ordering.EQUAL


def _modified_unix(info: Gio.FileInfo) -> int:
    dt = info.get_modification_date_time()
    if dt is None:
        return 0
    return dt.to_unix()


def _pane_row_string_sorter(path: str) -> Gtk.StringSorter:
    sorter = Gtk.StringSorter.new(Gtk.PropertyExpression(PaneRow, property_name=path))
    sorter.set_ignore_case(True)
    return sorter


def _pane_row_numeric_sorter(
    path: str,
    *,
    descending: bool = False,
) -> Gtk.NumericSorter:
    sorter = Gtk.NumericSorter.new(Gtk.PropertyExpression(PaneRow, property_name=path))
    sorter.set_sort_order(Gtk.SortType.DESCENDING if descending else Gtk.SortType.ASCENDING)
    return sorter


def _pane_row_multi_sorter(*sorters: Gtk.Sorter) -> Gtk.MultiSorter:
    sorter = Gtk.MultiSorter.new()
    for item in sorters:
        sorter.append(item)
    return sorter


def _pane_row_name_sorter() -> Gtk.MultiSorter:
    return _pane_row_multi_sorter(
        _pane_row_numeric_sorter("sort_bucket"),
        _pane_row_string_sorter("name_key"),
    )


def _pane_row_extension_sorter() -> Gtk.MultiSorter:
    return _pane_row_multi_sorter(
        _pane_row_numeric_sorter("sort_bucket"),
        _pane_row_string_sorter("ext_key"),
        _pane_row_string_sorter("name_key"),
    )


def _pane_row_size_sorter() -> Gtk.MultiSorter:
    return _pane_row_multi_sorter(
        _pane_row_numeric_sorter("sort_bucket"),
        _pane_row_numeric_sorter("size_key", descending=True),
        _pane_row_string_sorter("name_key"),
    )


def _pane_row_date_sorter() -> Gtk.MultiSorter:
    return _pane_row_multi_sorter(
        _pane_row_numeric_sorter("sort_bucket"),
        _pane_row_numeric_sorter("mtime_key", descending=True),
        _pane_row_string_sorter("name_key"),
    )


def _pane_row_attr_sorter() -> Gtk.MultiSorter:
    return _pane_row_multi_sorter(
        _pane_row_numeric_sorter("sort_bucket"),
        _pane_row_string_sorter("attr_key"),
        _pane_row_string_sorter("name_key"),
    )


def _pane_row_diff_key(
    row: PaneRow | None,
) -> tuple[str, int, bool, bool, str, str, int, int, str, str, str, str, str]:
    if row is None:
        return ("", 0, False, False, "", "", 0, 0, "", "", "", "", "")
    return (
        row.name,
        row.sort_bucket,
        row.is_parent,
        row.is_hidden,
        row.name_key,
        row.ext_key,
        row.size_key,
        row.mtime_key,
        row.attr_key,
        row.name_text,
        row.ext_text,
        row.size_text,
        row.date_text,
    )


class PaneRow(GObject.Object, type_name="CommanderPaneRow"):

    is_parent = GObject.Property(type=bool, default=False)
    is_hidden = GObject.Property(type=bool, default=False)
    sort_bucket = GObject.Property(type=int, default=0)
    name = GObject.Property(type=str, default="")
    name_key = GObject.Property(type=str, default="")
    ext_key = GObject.Property(type=str, default="")
    size_key = GObject.Property(type=GType.INT64, default=0)
    mtime_key = GObject.Property(type=GType.INT64, default=0)
    attr_key = GObject.Property(type=str, default="")
    name_text = GObject.Property(type=str, default="")
    ext_text = GObject.Property(type=str, default="")
    size_text = GObject.Property(type=str, default="")
    date_text = GObject.Property(type=str, default="")
    attr_text = GObject.Property(type=str, default="")

    def __init__(self, info: Gio.FileInfo) -> None:
        super().__init__()
        self.file_info = info
        is_parent = _is_parent_row(info)
        is_dir = _file_type_is_directory(info)
        stem, ext = _split_name(info)
        name = info.get_name() or ""

        self.is_parent = is_parent
        self.is_hidden = False if is_parent else bool(info.get_is_hidden())
        self.sort_bucket = 0 if is_parent else 1 if is_dir else 2
        self.name = name
        self.name_key = stem.strip("[]")
        self.ext_key = ext
        self.size_key = int(info.get_size())
        self.mtime_key = _modified_unix(info)
        self.attr_key = _format_attr(info)
        self.name_text = stem
        self.ext_text = ext
        self.size_text = _format_size(info)
        self.date_text = _format_mtime(info)
        self.attr_text = self.attr_key


class CommanderPane(Gtk.Box, type_name="GoiCommanderPane"):

    name_column: Gtk.ColumnViewColumn
    ext_column: Gtk.ColumnViewColumn
    size_column: Gtk.ColumnViewColumn
    date_column: Gtk.ColumnViewColumn
    attr_column: Gtk.ColumnViewColumn
    directory_list: Gtk.DirectoryList
    file_store: Gio.ListStore[PaneRow]
    filter_model: Gtk.FilterListModel[PaneRow]
    sort_model: Gtk.SortListModel[PaneRow]
    selection: Gtk.SingleSelection[PaneRow]
    location_choices: list[LocationChoice]
    parent_override: File | None
    virtual_files: dict[str, File] | None

    def __init__(
        self,
        side: str,
        *,
        initial_location: File | None = None,
        show_hidden_files: bool = False,
        on_location_changed: Callable[[CommanderPane, File], None] | None = None,
        on_focus_requested: Callable[[CommanderPane], None] | None = None,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.side = side
        self.current_dir = initial_location or File.from_path(str(Path.home()))
        self.show_hidden_files = show_hidden_files
        self.active = False
        self.location_choices = []
        self._syncing_location_switcher = False
        self.volume_monitor = Gio.VolumeMonitor.get()
        self._on_location_changed = on_location_changed
        self._on_focus_requested = on_focus_requested
        self.parent_override = None
        self.virtual_files = None
        self.virtual_items: list[PaneRow] = []
        self.virtual_temps: list[tempfile.TemporaryDirectory[str]] = []
        self._directory_refresh_pending = False
        self._pending_directory_list: Gtk.DirectoryList | None = None
        self._folder_selection_history: dict[str, str] = {}
        self._pending_selection_name: str | None = None
        self._folder_scroll_history: dict[str, float] = {}
        self._pending_scroll_value: float | None = None
        self._pending_focus_index: int | None = None

        self.add_css_class("commander-pane")

        self.header = self._build_header()
        self.path_row = self._build_path_row()
        self.directory_list = self._new_directory_list(self.current_dir)
        self.file_store = Gio.ListStore.new(PaneRow)
        self.hidden_filter_callback = self._filter_file
        self.hidden_filter = Gtk.CustomFilter.new(self.hidden_filter_callback)
        self.filter_model = Gtk.FilterListModel.new(self.file_store, self.hidden_filter)
        self.filter_model.set_incremental(False)
        self.sort_model = Gtk.SortListModel.new(self.filter_model, None)
        self.sort_model.set_incremental(False)
        self.selection = Gtk.SingleSelection.new(self.sort_model)
        self.selection.set_autoselect(True)
        self.selection.set_can_unselect(False)
        self.view = Gtk.ColumnView.new(self.selection)
        self.view.add_css_class("file-view")
        self.view.set_show_column_separators(False)
        self.view.set_show_row_separators(False)
        self.view.set_single_click_activate(False)
        self.view.activate.connect(self._on_view_activate)
        self._install_focus_tracking()

        self._add_columns()
        self.sort_model.set_sorter(self.view.get_sorter())
        self.view.sort_by_column(self.name_column, Gtk.SortType.ASCENDING)

        self.scroller = Gtk.ScrolledWindow()
        self.scroller.add_css_class("file-scroller")
        self.scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_child(self.view)
        self.scroller.set_vexpand(True)
        self.scroller.set_hexpand(True)

        self.status = Gtk.Label(xalign=0.0)
        self.status.add_css_class("pane-status")

        self.append(self.header)
        self.append(self.path_row)
        self.append(self.scroller)
        self.append(self.status)

        self._connect_volume_monitor()
        self._refresh_location_choices()
        self.set_location(self.current_dir, notify=False)

    def _build_header(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        row.add_css_class("pane-header")

        folder = Gtk.Image.new_from_icon_name("folder-symbolic")
        folder.add_css_class("pane-header-icon")
        self.location_model = Gtk.StringList.new(None)
        self.location_switcher = Gtk.DropDown.new(
            cast("Gio.ListModel[GObject.Object] | None", self.location_model),
            None,
        )
        self.location_switcher.add_css_class("location-switcher")
        self.location_switcher.set_enable_search(False)
        self.location_switcher.set_size_request(110, -1)
        self.location_switcher.notify("selected").connect(self._on_location_selected)

        self.free_label = Gtk.Label(xalign=0.0)
        self.free_label.set_hexpand(True)
        self.free_label.add_css_class("free-label")

        root = Gtk.Button.new_with_label("\\")
        root.add_css_class("tiny-command")
        root.clicked.connect(lambda *_: self.go_root())
        parent = Gtk.Button.new_with_label("..")
        parent.add_css_class("tiny-command")
        parent.clicked.connect(lambda *_: self.go_parent())

        row.append(folder)
        row.append(self.location_switcher)
        row.append(self.free_label)
        row.append(root)
        row.append(parent)
        return row

    def _build_path_row(self) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
        row.add_css_class("path-row")

        self.path_entry = Gtk.Entry()
        self.path_entry.set_has_frame(False)
        self.path_entry.set_hexpand(True)
        self.path_entry.activate.connect(self._on_path_activate)

        refresh = Gtk.Button.new_with_label("*")
        refresh.add_css_class("tiny-command")
        refresh.clicked.connect(lambda *_: self.refresh())

        menu = Gtk.Button.new_with_label("v")
        menu.add_css_class("tiny-command")

        row.append(self.path_entry)
        row.append(refresh)
        row.append(menu)
        return row

    def _add_columns(self) -> None:
        specs = (
            (
                "Name",
                self._make_name_factory(),
                self._make_name_sorter(),
                260,
                True,
                "name_column",
            ),
            (
                "Ext",
                self._make_text_factory("ext_text"),
                self._make_extension_sorter(),
                54,
                False,
                "ext_column",
            ),
            (
                "Size",
                self._make_text_factory("size_text", align=1.0, css_class="size-cell"),
                self._make_size_sorter(),
                96,
                False,
                "size_column",
            ),
            (
                "Date",
                self._make_text_factory("date_text"),
                self._make_date_sorter(),
                130,
                False,
                "date_column",
            ),
            (
                "Attr",
                self._make_text_factory("attr_text"),
                self._make_attr_sorter(),
                54,
                False,
                "attr_column",
            ),
        )
        for title, factory, sorter, width, expand, attr_name in specs:
            column = Gtk.ColumnViewColumn.new(title, factory)
            column.set_resizable(True)
            column.set_sorter(sorter)
            column.set_fixed_width(width)
            column.set_expand(expand)
            self.view.append_column(column)
            if attr_name is not None:
                setattr(self, attr_name, column)

    def _string_sorter(self, path: str) -> Gtk.StringSorter:
        return _pane_row_string_sorter(path)

    def _numeric_sorter(self, path: str, *, descending: bool = False) -> Gtk.NumericSorter:
        return _pane_row_numeric_sorter(path, descending=descending)

    def _multi_sorter(self, *sorters: Gtk.Sorter) -> Gtk.MultiSorter:
        return _pane_row_multi_sorter(*sorters)

    def _make_name_sorter(self) -> Gtk.MultiSorter:
        return _pane_row_name_sorter()

    def _make_extension_sorter(self) -> Gtk.MultiSorter:
        return _pane_row_extension_sorter()

    def _make_size_sorter(self) -> Gtk.MultiSorter:
        return _pane_row_size_sorter()

    def _make_date_sorter(self) -> Gtk.MultiSorter:
        return _pane_row_date_sorter()

    def _make_attr_sorter(self) -> Gtk.MultiSorter:
        return _pane_row_attr_sorter()

    def _filter_file(self, row: GObject.Object) -> bool:
        if not isinstance(row, PaneRow):
            return False
        if self.show_hidden_files or row.is_parent:
            return True
        return not row.is_hidden

    def _make_name_factory(self) -> Gtk.SignalListItemFactory:
        factory = Gtk.SignalListItemFactory.new()

        def setup(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=1)
            box.add_css_class("name-cell")
            image = Gtk.Image.new_from_icon_name("text-x-generic-symbolic")
            image.set_pixel_size(14)
            label = Gtk.Label(xalign=0.0)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            box.append(image)
            box.append(label)
            item.set_child(box)

        def bind(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
            obj = item.get_item()
            box = item.get_child()
            assert isinstance(obj, PaneRow) and box is not None
            image = box.get_first_child()
            assert isinstance(image, Gtk.Image)
            label = image.get_next_sibling()
            assert isinstance(label, Gtk.Label)
            info = obj.file_info
            icon = info.get_icon()
            if icon is not None:
                image.set_from_gicon(icon)
            label.set_text(obj.name_text)

        factory.setup.connect(setup)
        factory.bind.connect(bind)
        return factory

    def _make_text_factory(
        self,
        attr_name: str,
        align: float = 0.0,
        css_class: str = "text-cell",
    ) -> Gtk.SignalListItemFactory:
        factory = Gtk.SignalListItemFactory.new()

        def setup(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
            label = Gtk.Label(xalign=align)
            label.add_css_class(css_class)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            item.set_child(label)

        def bind(_factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
            row = item.get_item()
            label = item.get_child()
            assert isinstance(label, Gtk.Label)
            label.set_text(getattr(row, attr_name))

        factory.setup.connect(setup)
        factory.bind.connect(bind)
        return factory

    def set_active(self, active: bool) -> None:
        self.active = active
        if active:
            self.add_css_class("active-pane")
        else:
            self.remove_css_class("active-pane")

    def focus_file_view(self) -> None:
        self.view.grab_focus()

    def set_show_hidden_files(self, enabled: bool) -> None:
        value = bool(enabled)
        if self.show_hidden_files == value:
            return
        self.show_hidden_files = value
        self.hidden_filter.changed(Gtk.FilterChange.DIFFERENT)
        self._refresh_status()

    def sort_by_name(self) -> None:
        self.view.sort_by_column(self.name_column, Gtk.SortType.ASCENDING)

    def sort_by_extension(self) -> None:
        self.view.sort_by_column(self.ext_column, Gtk.SortType.ASCENDING)

    def sort_by_date(self) -> None:
        self.view.sort_by_column(self.date_column, Gtk.SortType.DESCENDING)

    def sort_by_size(self) -> None:
        self.view.sort_by_column(self.size_column, Gtk.SortType.DESCENDING)

    def _install_focus_tracking(self) -> None:
        for widget in (self.view, self.path_entry, self.location_switcher):
            focus = Gtk.EventControllerFocus.new()
            focus.enter.connect(self._on_focus_enter)
            widget.add_controller(focus)

        click = Gtk.GestureClick.new()
        click.set_button(0)
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.pressed.connect(self._on_click_pressed)
        self.add_controller(click)

    def _on_focus_enter(self, *_args: object) -> None:
        self.request_focus()

    def _on_click_pressed(self, *_args: object) -> None:
        self.request_focus()

    def request_focus(self) -> None:
        if self._on_focus_requested is not None:
            self._on_focus_requested(self)

    def set_location(self, file_: File, *, notify: bool = True) -> None:
        self._remember_scroll_position(self.current_dir)
        self.virtual_files = None
        self.virtual_items = []
        self.current_dir = file_
        self.parent_override = self._parent_override_for(file_)
        self._directory_refresh_pending = True
        self._pending_directory_list = self._new_directory_list(file_)
        self._pending_scroll_value = self._folder_scroll_history.get(file_.uri)
        self.path_entry.set_text(display_file(file_))
        self._sync_location_switcher()
        self._refresh_filesystem_info()
        self._refresh_status()
        if notify and self._on_location_changed is not None:
            self._on_location_changed(self, file_)

    def refresh(self) -> None:
        self._remember_scroll_position(self.current_dir)
        self._directory_refresh_pending = True
        self._pending_directory_list = self._new_directory_list(self.current_dir)
        self._pending_scroll_value = self._folder_scroll_history.get(self.current_dir.uri)
        self._refresh_filesystem_info()

    def go_home(self) -> None:
        self.set_location(File.from_path(str(Path.home())))

    def go_root(self) -> None:
        self.set_location(File.from_path("/"))

    def go_parent(self) -> None:
        parent = self.parent_file()
        if parent is not None:
            child_name = self.current_dir.basename
            if child_name:
                self._folder_selection_history[parent.uri] = child_name
                self._pending_selection_name = child_name
            self._remember_scroll_position(self.current_dir)
            self._pending_scroll_value = self._folder_scroll_history.get(parent.uri)
            self.set_location(parent)

    def parent_file(self) -> File | None:
        if self.virtual_files is not None:
            return self.parent_override
        return self.parent_override or self.current_dir.parent()

    def _parent_override_for(self, file_: File) -> File | None:
        archive_file = archive_file_for_root(file_)
        if archive_file is None:
            return None
        return archive_file.parent()

    def _refresh_location_choices(self) -> None:
        self.location_choices = list_location_choices()
        self._syncing_location_switcher = True
        while self.location_model.get_n_items() > 0:
            self.location_model.remove(0)
        for choice in self.location_choices:
            self.location_model.append(choice.label)
        self._syncing_location_switcher = False
        self._sync_location_switcher()

    def _connect_volume_monitor(self) -> None:
        for signal_name in (
            "mount-added",
            "mount-removed",
            "mount-changed",
            "volume-added",
            "volume-removed",
            "volume-changed",
        ):
            try:
                self.volume_monitor.connect(
                    signal_name, lambda *_args: self._refresh_location_choices()
                )
            except TypeError:
                pass

    def _sync_location_switcher(self) -> None:
        if not self.location_choices:
            return
        index = choose_location_index(self.location_choices, self.current_dir)
        self._syncing_location_switcher = True
        self.location_switcher.set_selected(index)
        self._syncing_location_switcher = False

    def _on_location_selected(self, switcher: Gtk.DropDown, /, *_args: object) -> None:
        if self._syncing_location_switcher:
            return
        index = switcher.get_selected()
        if index >= len(self.location_choices):
            return
        self.set_location(self.location_choices[index].file)

    def _on_directory_items_changed(self, model: Gtk.DirectoryList, *_args: object) -> None:
        if self.virtual_files is not None:
            return
        if self._directory_refresh_pending and model is self._pending_directory_list:
            if model.get_property("loading") and model.get_n_items() == 0:
                self._refresh_status()
                return
            self._activate_pending_directory_list()
        elif model is self.directory_list:
            self._load_snapshot(self._directory_snapshot(self.directory_list))
        self._refresh_status()

    def _new_directory_list(self, file_: File) -> Gtk.DirectoryList:
        model = Gtk.DirectoryList.new(FILE_ATTRIBUTES, file_.gio)
        model.set_monitored(True)
        model.items_changed.connect(self._on_directory_items_changed)
        model.notify("loading").connect(self._refresh_status)
        return model

    def _activate_pending_directory_list(self) -> None:
        if self._pending_directory_list is None:
            return
        pending = self._pending_directory_list
        self._load_snapshot(self._directory_snapshot(pending))
        self.directory_list = pending
        self._pending_directory_list = None
        self._directory_refresh_pending = False
        self._restore_pending_selection()

    def _directory_snapshot(self, model: Gtk.DirectoryList | None = None) -> list[PaneRow]:
        snapshot: list[PaneRow] = []
        if self.parent_file() is not None:
            snapshot.append(PaneRow(_make_parent_info()))
        source = self.directory_list if model is None else model
        for index in range(source.get_n_items()):
            item = source.get_item(index)
            if item is not None:
                snapshot.append(PaneRow(item))
        return snapshot

    def _load_snapshot(self, snapshot: list[PaneRow]) -> None:
        current = [
            cast("PaneRow", self.file_store.get_item(i))
            for i in range(self.file_store.get_n_items())
        ]
        prefix = 0
        while prefix < len(current) and prefix < len(snapshot):
            if self._info_key(current[prefix]) != self._info_key(snapshot[prefix]):
                break
            prefix += 1
        current_suffix = len(current)
        snapshot_suffix = len(snapshot)
        while current_suffix > prefix and snapshot_suffix > prefix:
            if self._info_key(current[current_suffix - 1]) != self._info_key(
                snapshot[snapshot_suffix - 1]
            ):
                break
            current_suffix -= 1
            snapshot_suffix -= 1
        self.file_store.splice(
            prefix,
            current_suffix - prefix,
            snapshot[prefix:snapshot_suffix],
        )

    def _info_key(
        self, row: PaneRow | None
    ) -> tuple[str, int, bool, bool, str, str, int, int, str, str, str, str, str]:
        return _pane_row_diff_key(row)

    def _restore_pending_selection(self) -> None:
        name = self._pending_selection_name
        if name:
            model = cast("Gio.ListModel[PaneRow]", self.sort_model)
            for index in range(len(model)):
                row = model[index]
                if row is not None and row.name == name:
                    self.selection.set_selected(index)
                    self._pending_selection_name = None
                    self._pending_focus_index = index
                    break
        self._restore_pending_scroll()

    def _remember_scroll_position(self, file_: File | None) -> None:
        if file_ is None:
            return
        adjustment = self.scroller.get_vadjustment()
        if adjustment is None:
            return
        self._folder_scroll_history[file_.uri] = adjustment.get_value()

    def _restore_pending_scroll(self) -> None:
        if self._pending_scroll_value is None and self._pending_focus_index is None:
            return
        adjustment = self.scroller.get_vadjustment()
        if adjustment is None:
            return
        value = self._pending_scroll_value
        self._pending_scroll_value = None
        focus_index = self._pending_focus_index
        self._pending_focus_index = None

        def apply_scroll() -> bool:
            if focus_index is not None:
                self.view.grab_focus()
                self.view.scroll_to(
                    focus_index,
                    None,
                    Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT,
                    None,
                )
            if value is not None:
                upper = adjustment.get_upper()
                page_size = adjustment.get_page_size()
                max_value = max(0.0, upper - page_size)
                adjustment.set_value(min(value, max_value))
            return False

        GLib.idle_add(apply_scroll)

    def activate_selected(self) -> None:
        row = self.selection.get_selected_item()
        if row is None:
            return
        self._activate_row(row)

    def enter_selected_archive(self) -> bool:
        file_ = self.selected_file()
        if file_ is None:
            self.status.set_text("No file selected")
            return False
        if is_plain_gzip(file_):
            return self._enter_gzip(file_)
        return enter_archive(
            file_,
            on_ready=self.set_location,
            on_error=self.status.set_text,
        )

    def _enter_gzip(self, file_: File) -> bool:
        try:
            tempdir, member = extract_gzip_member(file_)
            info = member.query_info(FILE_ATTRIBUTES, Gio.FileQueryInfoFlags.NONE)
        except _GZIP_ERRORS as error:
            self.status.set_text(f"Gzip open failed: {error}")
            return False

        name = gzip_member_name(file_)
        info.set_name(name)
        info.set_display_name(name)
        self.virtual_temps.append(tempdir)
        self.virtual_files = {name: member}
        row = PaneRow(info)
        self.virtual_items = [row]
        self.current_dir = file_
        self.parent_override = file_.parent()
        self._pending_directory_list = None
        self._directory_refresh_pending = False
        snapshot: list[PaneRow] = []
        if self.parent_file() is not None:
            snapshot.append(PaneRow(_make_parent_info()))
        snapshot.append(row)
        self._load_snapshot(snapshot)
        self.directory_list.set_file(None)
        self.path_entry.set_text(display_file(file_))
        self._sync_location_switcher()
        self._refresh_filesystem_info()
        self._refresh_status()
        if self._on_location_changed is not None:
            self._on_location_changed(self, file_)
        return True

    def selected_is_parent_row(self) -> bool:
        row = self.selection.get_selected_item()
        return bool(row is not None and row.is_parent)

    def selected_info(self) -> Gio.FileInfo | None:
        row = self.selection.get_selected_item()
        return None if row is None else row.file_info

    def selected_file(self) -> File | None:
        row = self.selection.get_selected_item()
        if row is None:
            return None
        if row.is_parent:
            return self.parent_file()
        name = row.name
        if self.virtual_files is not None:
            return self.virtual_files.get(name or "")
        return self.current_dir.child(name) if name else None

    def _on_view_activate(self, _view: Gtk.ColumnView, position: int) -> None:
        model = cast("Gio.ListModel[PaneRow]", self.sort_model)
        for index in range(len(model)):
            row = model[index]
            if index == position:
                self._activate_row(row)
                break

    def _activate_row(self, row: PaneRow) -> None:
        if row.is_parent:
            self.go_parent()
            return
        name = row.name
        if not name:
            return
        if self.virtual_files is not None:
            return
        target = self.current_dir.child(name)
        if row.sort_bucket == 1:
            self.set_location(target)
            return
        target.launch_default()

    def _on_path_activate(self, entry: Gtk.Entry) -> None:
        text = entry.get_text().strip()
        if not text:
            return
        text = expand_home(text)
        if "://" in text:
            self.set_location(File.from_uri(text))
        else:
            self.set_location(File.from_path(text))

    def _refresh_filesystem_info(self, *_args: object) -> None:
        if self.virtual_files is not None:
            self.free_label.set_text("[archive]  virtual gzip view")
            return
        try:
            info = self.current_dir.query_filesystem_info(FS_ATTRIBUTES)
            free = info.get_attribute_uint64("filesystem::free") // 1024
            size = info.get_attribute_uint64("filesystem::size") // 1024
            self.free_label.set_text(
                f"[_none_]  {_format_bytes(free)} of {_format_bytes(size)} free"
            )
        except GLib.Error:
            self.free_label.set_text("[_none_]  space unavailable")

    def _refresh_status(self, *_args: object) -> None:
        if self.virtual_files is not None:
            total = len(self.virtual_items)
            loading = ""
        else:
            loading_model = self._pending_directory_list or self.directory_list
            if self._directory_refresh_pending and not loading_model.get_property("loading"):
                self._activate_pending_directory_list()
                loading_model = self.directory_list
            self._restore_pending_selection()
            total = loading_model.get_n_items()
            loading = " loading" if loading_model.get_property("loading") else ""
        self.status.set_text(f"0 k / 0 k in 0 / 0 file(s), 0 / {total} item(s){loading}")
