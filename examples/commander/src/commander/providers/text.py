from __future__ import annotations

import sys

from ginext import Gio, GLib, Gtk

from commander.fs import File
from commander.providers.base import CommanderProviderContext, ProviderCapability

MAX_TEXT_BYTES = 4 * 1024 * 1024
TEXT_CONTENT_PREFIX = "text/"
SOURCE_CONTENT_TYPES = (
    "application/javascript",
    "application/json",
    "application/x-python-code",
    "application/xml",
)


class TextProvider:
    id = "text"
    label = "Text"
    priority = 100
    capabilities = (ProviderCapability.QUICK_VIEW,)

    def supports(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> bool:
        content_type = info.get_content_type() or ""
        return content_type.startswith(TEXT_CONTENT_PREFIX) or any(
            Gio.content_type_is_mime_type(content_type, item) for item in SOURCE_CONTENT_TYPES
        )

    def create_widget(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> Gtk.Widget:
        if info.get_size() > MAX_TEXT_BYTES:
            return _message("Text file is too large for quick view")

        try:
            contents = file.load_contents()
        except GLib.Error as error:
            return _message(f"Unable to load text file: {error.message}")

        text = contents.decode("utf-8", errors="replace")
        view = _build_source_view(file, info, text) or _build_plain_view(text)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        scroller.set_child(view)
        return scroller


def _build_source_view(file: File, info: Gio.FileInfo, text: str) -> Gtk.Widget | None:
    try:
        from ginext import GtkSource
    except ImportError as error:
        print(f"[commander] GtkSource unavailable: {error}", file=sys.stderr)
        return None

    source_buffer = GtkSource.Buffer.new(None)
    source_buffer.set_highlight_syntax(True)
    manager = GtkSource.LanguageManager.get_default()
    language = manager.guess_language(
        file.basename or "",
        info.get_content_type() or None,
    )
    if language is not None:
        source_buffer.set_language(language)
    source_buffer.set_text(text, -1)
    view: Gtk.TextView = GtkSource.View.new_with_buffer(source_buffer)

    _configure_text_view(view)
    return view


def _build_plain_view(text: str) -> Gtk.Widget:
    text_buffer = Gtk.TextBuffer.new(None)
    text_buffer.set_text(text, -1)
    view = Gtk.TextView.new_with_buffer(text_buffer)
    _configure_text_view(view)
    return view


def _configure_text_view(view: Gtk.TextView) -> None:
    view.add_css_class("quick-view-text")
    view.set_editable(False)
    view.set_cursor_visible(False)
    view.set_wrap_mode(Gtk.WrapMode.NONE)
    view.set_monospace(True)
    view.set_hexpand(True)
    view.set_vexpand(True)


def _message(message: str) -> Gtk.Widget:
    label = Gtk.Label(label=message, xalign=0.0, yalign=0.0)
    label.set_selectable(True)
    label.set_wrap(True)
    label.set_hexpand(True)
    label.set_vexpand(True)
    return label
