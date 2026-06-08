from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cairo
from ginext import Gdk, Gio, GLib, Gtk, PangoCairo

from commander.components.location import display_file
from commander.components.pangoutils import measure_text_metrics
from commander.fs import File

FileSize = int
FileMode = str
PercentChangedFn = Callable[[int, int], None]
StatusChangedFn = Callable[[str, int, int, int], None]

_COMPONENT_DIR = Path(__file__).resolve().parent
_READ_SIZE = 512 * 1024
_MAX_LINE_BYTES = 4096
_TEXT_MIME_TYPES = (
    "application/javascript",
    "application/json",
    "application/xml",
    "application/x-python-code",
)
_MODE_TEXT = "text"
_MODE_BINARY = "binary"
_MODE_HEX = "hex"
_WRAP_COLUMNS = 80
_HEX_BYTES_PER_ROW = 16
_TEXT_ANCHOR_SCAN = 128 * 1024
_BINARY_TRANSLATION = {codepoint: "." for codepoint in (*range(0x00, 0x20), *range(0x7F, 0xA0))}


@dataclass
class RenderLine:
    text: str
    next_offset: int


class ByteWindow:
    def __init__(self, file: File, file_size: int) -> None:
        self.file = file
        self.file_size = file_size
        self.stream: Gio.FileInputStream | None = None
        self.seekable: Gio.FileInputStream | None = None
        self.base_offset = 0
        self.data = b""
        self._open_stream()

    def _open_stream(self) -> None:
        self.stream = self.file.read_stream()
        can_seek = getattr(self.stream, "can_seek", None)
        if can_seek is not None and can_seek():
            self.seekable = self.stream

    @property
    def can_seek(self) -> bool:
        return self.seekable is not None

    def close(self) -> None:
        if self.stream is not None:
            try:
                self.stream.close(None)
            except GLib.Error:
                pass
            self.stream = None
            self.seekable = None
            self.base_offset = 0
            self.data = b""

    def read_at(self, offset: int, size: int = _READ_SIZE) -> bytes:
        offset = max(0, min(offset, max(0, self.file_size)))
        size = max(0, min(size, self.file_size - offset))
        if size <= 0:
            return b""
        if self._contains(offset, size):
            start = offset - self.base_offset
            return self.data[start : start + size]
        if self.can_seek:
            try:
                assert self.seekable is not None
                self.seekable.seek(offset, GLib.SeekType.SET, None)
                self.base_offset = offset
                self.data = self._read(size)
                return self.data
            except GLib.Error:
                self.seekable = None
                return self._reopen_and_read(offset, size)
        if offset < self.base_offset:
            return self._reopen_and_read(offset, size)
        if offset > self.base_offset + len(self.data):
            skipped = self._skip_forward(offset - (self.base_offset + len(self.data)))
            if skipped < offset - (self.base_offset + len(self.data)):
                self.base_offset = min(self.file_size, self.base_offset + len(self.data) + skipped)
                self.data = b""
                return b""
        self.base_offset = offset
        self.data = self._read(size)
        return self.data

    def _contains(self, offset: int, size: int) -> bool:
        return self.base_offset <= offset and offset + size <= self.base_offset + len(self.data)

    def _read(self, size: int) -> bytes:
        if self.stream is None or size <= 0:
            return b""
        return self.stream.read_bytes(size, None).get_data()

    def _reopen_and_read(self, offset: int, size: int) -> bytes:
        self.close()
        self._open_stream()
        skipped = self._skip_forward(offset)
        if skipped < offset:
            self.base_offset = min(self.file_size, skipped)
            self.data = b""
            return b""
        self.base_offset = offset
        self.data = self._read(size)
        return self.data

    def _skip_forward(self, count: int) -> int:
        remaining = count
        while remaining > 0:
            data = self._read(min(remaining, _READ_SIZE))
            if not data:
                break
            remaining -= len(data)
        return count - remaining


class VirtualListerView(Gtk.DrawingArea, type_name="GoiCommanderVirtualListerView"):

    def __init__(
        self,
        byte_window: ByteWindow,
        adjustment: Gtk.Adjustment,
        percent_changed: PercentChangedFn,
        status_changed: StatusChangedFn,
        *,
        mode: str,
    ) -> None:
        super().__init__()
        self.byte_window = byte_window
        self.adjustment = adjustment
        self.percent_changed = percent_changed
        self.status_changed = status_changed
        self.mode = mode
        self.offset = 0
        self.line_height = 1
        self.char_width = 1
        self.columns_width = 1
        self.visible_byte_span = 1
        self.visible_rows = 1
        self._requested_content_width = 0
        self._padding_top = 0
        self._padding_right = 0
        self._padding_bottom = 0
        self._padding_left = 0
        self._pending_render_state: tuple[int, int, int] | None = None
        self._render_state_source = 0
        self.set_focusable(True)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.add_css_class("lister-view")
        self.set_draw_func(self._draw)
        self.update_layout_metrics()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.set_offset(self.offset)

    def set_offset(self, offset: int, *, update_adjustment: bool = True) -> None:
        file_size = self.byte_window.file_size
        self.offset = self._normalize_offset(max(0, min(offset, self._max_top_offset(file_size))))
        if update_adjustment and abs(self.adjustment.get_value() - self.offset) > 1:
            self.adjustment.set_value(self.offset)
        self.queue_draw()
        self.percent_changed(self.offset, file_size)

    def scroll_rows(self, rows: int) -> None:
        if rows == 0:
            return
        if self.mode in (_MODE_BINARY, _MODE_HEX):
            stride = max(1, self._bytes_per_row())
            self.set_offset(self.offset + rows * stride)
            return
        self.set_offset(self._text_offset_by_rows(rows))

    def page_rows(self, direction: int) -> None:
        rows = max(1, self.get_allocated_height() // self.line_height - 1)
        self.scroll_rows(rows * direction)

    def _draw(
        self,
        _area: Gtk.DrawingArea,
        cr: cairo.Context[cairo.Surface],
        width: int,
        height: int,
    ) -> None:
        cr.set_source_rgb(1, 1, 1)
        cr.paint()

        layout = self.create_pango_layout("")
        self._update_layout_metrics(layout)
        content_height = max(1, height - self._padding_top - self._padding_bottom)
        visible_rows = max(1, content_height // self.line_height)
        lines = self._render_lines(visible_rows)

        cr.set_source_rgb(0, 0, 0)
        y = self._padding_top
        visible_last_offset = self.offset
        for line in lines:
            layout.set_text(line.text, -1)
            cr.move_to(self._padding_left, y)
            PangoCairo.show_layout(cr, layout)
            y += self.line_height
            visible_last_offset = line.next_offset

        self._queue_render_state(height, visible_rows, visible_last_offset)

    def update_layout_metrics(self) -> None:
        layout = self.create_pango_layout("")
        self._update_layout_metrics(layout)

    def _update_layout_metrics(self, layout: Any) -> None:
        metrics = measure_text_metrics(
            self,
            layout,
            columns=_WRAP_COLUMNS,
        )
        self._padding_top = metrics.padding_top
        self._padding_right = metrics.padding_right
        self._padding_bottom = metrics.padding_bottom
        self._padding_left = metrics.padding_left
        self.char_width = metrics.char_width
        self.columns_width = metrics.columns_width
        self.line_height = metrics.line_height
        self._update_content_width_request()

    def _update_content_width_request(self) -> None:
        width = self._padding_left + self.columns_width + self._padding_right
        if width != self._requested_content_width:
            self._requested_content_width = width
            self.set_size_request(width, -1)

    def _binary_lines(self, rows: int) -> list[RenderLine]:
        bytes_per_row = self._bytes_per_row()
        data = self.byte_window.read_at(self.offset, rows * bytes_per_row)
        lines = []
        cursor = self.offset
        for index in range(0, len(data), bytes_per_row):
            chunk = data[index : index + bytes_per_row]
            lines.append(RenderLine(_binary_text(chunk), cursor + len(chunk)))
            cursor += len(chunk)
        return lines

    def _hex_lines(self, rows: int) -> list[RenderLine]:
        bytes_per_row = self._bytes_per_row()
        data = self.byte_window.read_at(self.offset, rows * bytes_per_row)
        lines = []
        cursor = self.offset
        for index in range(0, len(data), bytes_per_row):
            chunk = data[index : index + bytes_per_row]
            lines.append(RenderLine(_hex_text(cursor, chunk), cursor + len(chunk)))
            cursor += len(chunk)
        return lines

    def _render_lines(self, rows: int) -> list[RenderLine]:
        match self.mode:
            case "binary":
                return self._binary_lines(rows)
            case "hex":
                return self._hex_lines(rows)
            case _:
                return self._text_lines(rows)

    def _text_lines(self, rows: int) -> list[RenderLine]:
        data = self.byte_window.read_at(self.offset)
        lines: list[RenderLine] = []
        cursor = self.offset
        index = 0
        while len(lines) < rows and index < len(data):
            end = self._text_chunk_end(data, index)
            chunk = data[index:end]
            lines.append(
                RenderLine(chunk.decode("utf-8", "replace").rstrip("\r\n"), cursor + len(chunk))
            )
            cursor += len(chunk)
            index = end
        return lines

    def _text_offset_by_rows(self, rows: int) -> int:
        if rows < 0:
            return self._previous_text_offset(self.offset, -rows)
        data = self.byte_window.read_at(self.offset)
        cursor = self.offset
        index = 0
        for _row in range(rows):
            end = self._text_chunk_end(data, index)
            if end <= index:
                break
            cursor += end - index
            index = end
        return cursor

    def _normalize_offset(self, offset: int) -> int:
        file_size = self.byte_window.file_size
        if offset >= file_size and file_size > 0:
            offset = file_size - 1
        if self.mode in (_MODE_BINARY, _MODE_HEX):
            return offset - (offset % self._bytes_per_row())
        return self._text_row_start_at_or_before(offset)

    def _previous_text_offset(self, offset: int, rows: int) -> int:
        cursor = offset
        for _row in range(rows):
            if cursor <= 0:
                return 0
            cursor = self._text_row_start_at_or_before(cursor - 1)
        return cursor

    def _text_row_start_at_or_before(self, offset: int) -> int:
        if offset <= 0:
            return 0
        file_size = self.byte_window.file_size
        offset = min(offset, file_size)
        scan_start = max(0, offset - _TEXT_ANCHOR_SCAN)
        data = self.byte_window.read_at(scan_start, offset - scan_start)
        local_offset = offset - scan_start
        line_start = self._line_start_for_offset(data, scan_start, local_offset)
        return line_start + ((offset - line_start) // _WRAP_COLUMNS) * _WRAP_COLUMNS

    def _line_start_for_offset(self, data: bytes, scan_start: int, local_offset: int) -> int:
        newline = data.rfind(b"\n", 0, local_offset)
        if newline >= 0:
            return scan_start + newline + 1
        if scan_start == 0:
            return 0
        return max(0, scan_start - (scan_start % _WRAP_COLUMNS))

    def _text_chunk_end(self, data: bytes, index: int) -> int:
        line_limit = min(len(data), index + _MAX_LINE_BYTES)
        wrap_limit = min(line_limit, index + _WRAP_COLUMNS)
        newline = data.find(b"\n", index, min(line_limit, wrap_limit + 1))
        if newline >= 0:
            return newline + 1
        return wrap_limit

    def _bytes_per_row(self) -> int:
        return _HEX_BYTES_PER_ROW if self.mode == _MODE_HEX else _WRAP_COLUMNS

    def _refresh_adjustment(self, height: int, visible_rows: int, last_offset: int) -> None:
        file_size = self.byte_window.file_size
        upper = max(1, file_size)
        visible = last_offset - self.offset
        if visible <= 0 or last_offset >= file_size:
            visible = self.visible_byte_span
        if visible <= 0:
            visible = self._estimated_visible_byte_span(height)
        page = max(1, min(upper, visible))
        self.visible_byte_span = page
        self.visible_rows = visible_rows
        max_top = self._max_top_offset(file_size, visible_rows)
        upper = max(1, max_top + page)
        self.adjustment.set_lower(0)
        self.adjustment.set_upper(upper)
        self.adjustment.set_page_size(page)
        self.adjustment.set_step_increment(max(1, page // visible_rows))
        self.adjustment.set_page_increment(page)
        if self.offset > max_top:
            self.set_offset(max_top)

    def _queue_render_state(self, height: int, visible_rows: int, last_offset: int) -> None:
        self._pending_render_state = (height, visible_rows, last_offset)
        if self._render_state_source == 0:
            source = GLib.idle_source_new()
            source.set_callback(self._flush_render_state)
            self._render_state_source = source.attach(GLib.MainContext.default())

    def _flush_render_state(self) -> bool:
        self._render_state_source = 0
        if self._pending_render_state is None:
            return False
        height, visible_rows, last_offset = self._pending_render_state
        self._pending_render_state = None
        self._refresh_adjustment(height, visible_rows, last_offset)
        self.percent_changed(self.offset, self.byte_window.file_size)
        self.status_changed(self.mode, self.offset, self.byte_window.file_size, last_offset)
        return False

    def _estimated_visible_byte_span(self, height: int) -> int:
        content_height = max(1, height - self._padding_top - self._padding_bottom)
        rows = max(1, content_height // self.line_height)
        if self.mode in (_MODE_BINARY, _MODE_HEX):
            return rows * self._bytes_per_row()
        return rows * _WRAP_COLUMNS

    def _max_top_offset(self, file_size: int | None = None, visible_rows: int | None = None) -> int:
        file_size = self.byte_window.file_size if file_size is None else file_size
        if file_size <= 0:
            return 0
        rows = max(1, visible_rows if visible_rows is not None else self.visible_rows)
        if self.mode in (_MODE_BINARY, _MODE_HEX):
            return max(0, file_size - rows * self._bytes_per_row())
        return self._previous_text_offset(file_size, rows)


class ListerWindow(Gtk.ApplicationWindow, type_name="GoiCommanderListerWindow"):

    def __init__(
        self,
        application: Gtk.Application,
        file: File,
        info: Gio.FileInfo,
    ) -> None:
        title = f"Lister - [{display_file(file)}]"
        super().__init__(application=application, title=title)
        self.app = application
        self.file = file
        self.info = info
        self.file_size = info.get_size()
        self.mode = _default_mode(info)
        self.byte_window = ByteWindow(file, self.file_size)
        self.syncing_adjustment = False
        self.set_default_size(-1, 890)

        self._load_css()
        self._install_actions()
        self.set_child(self._build_root())
        self.close_request.connect(self._on_close_request)
        self.view.grab_focus()

    def _load_css(self) -> None:
        provider = Gtk.CssProvider.new()
        provider.load_from_string((_COMPONENT_DIR / "listerview.css").read_text())
        display = Gdk.Display.get_default()
        if display is not None:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

    def _install_actions(self) -> None:
        action = Gio.SimpleAction.new("close-lister", None)
        action.activate.connect(lambda *_args: self.close())
        self.add_action(action)
        noop = Gio.SimpleAction.new("lister-noop", None)
        noop.activate.connect(lambda *_args: None)
        self.add_action(noop)
        text_mode = Gio.SimpleAction.new("lister-text-mode", None)
        text_mode.activate.connect(lambda *_args: self.set_mode(_MODE_TEXT))
        self.add_action(text_mode)
        binary_mode = Gio.SimpleAction.new("lister-binary-mode", None)
        binary_mode.activate.connect(lambda *_args: self.set_mode(_MODE_BINARY))
        self.add_action(binary_mode)
        hex_mode = Gio.SimpleAction.new("lister-hex-mode", None)
        hex_mode.activate.connect(lambda *_args: self.set_mode(_MODE_HEX))
        self.add_action(hex_mode)
        self.app.set_accels_for_action("win.close-lister", ["F3", "Escape"])
        self.app.set_accels_for_action("win.lister-text-mode", ["1"])
        self.app.set_accels_for_action("win.lister-binary-mode", ["2"])
        self.app.set_accels_for_action("win.lister-hex-mode", ["3"])

        controller = Gtk.EventControllerKey.new()
        controller.key_pressed.connect(self._on_key_pressed)
        self.add_controller(controller)

    def _build_root(self) -> Gtk.Widget:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("lister-root")
        root.append(self._build_menu_bar())

        upper = max(1, self.file_size, 4096)
        page_size = min(4096, upper)
        self.adjustment = Gtk.Adjustment(
            value=0,
            lower=0,
            upper=upper,
            step_increment=1,
            page_increment=page_size,
            page_size=page_size,
        )
        self.view = VirtualListerView(
            self.byte_window,
            self.adjustment,
            self._update_percent,
            self._set_render_status,
            mode=self.mode,
        )

        controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        controller.scroll.connect(self._on_scroll)
        self.view.add_controller(controller)

        viewport = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        viewport.set_hexpand(True)
        viewport.set_vexpand(True)
        viewport.append(self.view)
        self.scrollbar = Gtk.Scrollbar.new(Gtk.Orientation.VERTICAL, self.adjustment)
        self.scrollbar.set_vexpand(True)
        viewport.append(self.scrollbar)
        root.append(viewport)

        self.adjustment.value_changed.connect(self._on_adjustment_changed)

        self.status = Gtk.Label(xalign=0.0)
        self.status.add_css_class("lister-status")
        root.append(self.status)
        return root

    def _build_menu_bar(self) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row.add_css_class("lister-menu-row")

        menubar = Gio.Menu()
        for title, entries in (
            ("File", (("Close", "win.close-lister"),)),
            ("Edit", (("Copy", "win.lister-noop"),)),
            (
                "Options",
                (
                    ("Text 1", "win.lister-text-mode"),
                    ("Binary 2", "win.lister-binary-mode"),
                    ("Hex 3", "win.lister-hex-mode"),
                    ("Wrap text", "win.lister-noop"),
                ),
            ),
            ("Plugins", (("Configure", "win.lister-noop"),)),
            ("Encoding", (("UTF-8", "win.lister-noop"),)),
            ("Help", (("Keyboard", "win.lister-noop"),)),
        ):
            menu = Gio.Menu()
            for label, detailed_action in entries:
                menu.append(label, detailed_action)
            menubar.append_submenu(title, menu)

        menu_widget = Gtk.PopoverMenuBar.new_from_model(menubar)
        menu_widget.add_css_class("compact-menu")
        menu_widget.set_hexpand(True)
        row.append(menu_widget)

        self.percent_label = Gtk.Label(label="0 %", xalign=1.0)
        self.percent_label.add_css_class("lister-percent")
        row.append(self.percent_label)
        return row

    def set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self.view.set_mode(mode)

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        match keyval:
            case Gdk.KEY_F3 | Gdk.KEY_Escape:
                self.close()
                return True
            case Gdk.KEY_Down:
                self.view.scroll_rows(1)
                return True
            case Gdk.KEY_Up:
                self.view.scroll_rows(-1)
                return True
            case Gdk.KEY_Page_Down:
                self.view.page_rows(1)
                return True
            case Gdk.KEY_Page_Up:
                self.view.page_rows(-1)
                return True
            case Gdk.KEY_End:
                self.view.set_offset(max(0, self.file_size))
                return True
            case Gdk.KEY_Home:
                self.view.set_offset(0)
                return True
            case Gdk.KEY_1 | Gdk.KEY_KP_1:
                self.set_mode(_MODE_TEXT)
                return True
            case Gdk.KEY_2 | Gdk.KEY_KP_2:
                self.set_mode(_MODE_BINARY)
                return True
            case Gdk.KEY_3 | Gdk.KEY_KP_3:
                self.set_mode(_MODE_HEX)
                return True
        return False

    def _on_scroll(
        self,
        _controller: Gtk.EventControllerScroll,
        _dx: float,
        dy: float,
    ) -> bool:
        if dy < 0:
            self.view.scroll_rows(-3)
        elif dy > 0:
            self.view.scroll_rows(3)
        return True

    def _on_adjustment_changed(self, adjustment: Gtk.Adjustment) -> None:
        value = int(adjustment.get_value())
        if value != self.view.offset:
            self.view.set_offset(value, update_adjustment=False)

    def _update_percent(self, offset: int, file_size: int) -> None:
        if file_size > 0:
            percent = min(100, int((offset * 100) / file_size))
        else:
            percent = 100
        self.percent_label.set_text(f"{percent} %")

    def _set_render_status(self, mode: str, offset: int, file_size: int, last_offset: int) -> None:
        visible = max(0, last_offset - offset)
        self.status.set_text(
            f"{mode.title()}: offset {_format_bytes(offset)} / {_format_bytes(file_size)}, "
            f"visible {_format_bytes(visible)}"
        )

    def _on_close_request(self, *_args: object) -> bool:
        self.byte_window.close()
        return False


def _format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    size = float(value)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024.0
        if size < 1024.0:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} PB"


def _default_mode(info: Gio.FileInfo) -> str:
    return _MODE_TEXT if _is_text_content(info) else _MODE_BINARY


def _is_text_content(info: Gio.FileInfo) -> bool:
    content_type = info.get_content_type() or ""
    if content_type.startswith("text/"):
        return True
    return any(Gio.content_type_is_mime_type(content_type, mime) for mime in _TEXT_MIME_TYPES)


def _binary_text(data: bytes) -> str:
    return data.decode("latin-1").translate(_BINARY_TRANSLATION)


def _hex_text(offset: int, data: bytes) -> str:
    hex_bytes = " ".join(f"{byte:02X}" for byte in data)
    padded_hex = hex_bytes.ljust(_HEX_BYTES_PER_ROW * 3 - 1)
    ascii_text = _binary_text(data)
    return f"{offset:08X}  {padded_hex}  {ascii_text}"
