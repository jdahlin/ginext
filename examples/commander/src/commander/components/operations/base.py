from __future__ import annotations

from collections.abc import Callable
from typing import cast

from ginext import GLib, Gtk

from commander.fs import File
from commander.ui.gtkbuilder import get_widget, load_builder


class OperationDialog:
    def __init__(
        self,
        window: Gtk.Window,
        *,
        title: str,
        accept_label: str,
        message: str,
        initial_value: str,
        failure_title: str,
        success_message: str,
        set_status: Callable[[str], None],
        on_success: Callable[[File], None],
        perform: Callable[[str], File],
    ) -> None:
        self.window = window
        self.failure_title = failure_title
        self.success_message = success_message
        self.set_status = set_status
        self.on_success = on_success
        self.perform = perform

        builder = load_builder("operations.ui")
        self.root = get_widget(builder, "operation_root", Gtk.Widget)
        self.message_label = get_widget(builder, "message_label", Gtk.Label)
        self.value_entry = get_widget(builder, "value_entry", Gtk.Entry)

        self.message_label.set_text(message)
        self.value_entry.set_text(initial_value)

        self.dialog = Gtk.Dialog.new()
        self.dialog.set_title(title)
        self.dialog.set_transient_for(window)
        self.dialog.set_modal(True)
        self.dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        self.dialog.add_button(accept_label, Gtk.ResponseType.OK)
        self.dialog.set_default_response(Gtk.ResponseType.OK)
        self.dialog.get_content_area().append(self.root)
        self.dialog.response.connect(self._on_response)

    def present(self) -> None:
        self.dialog.present()
        self.value_entry.grab_focus()
        self.value_entry.select_region(0, -1)

    def _on_response(self, _dialog: Gtk.Dialog, response_id: int) -> None:
        try:
            if response_id != Gtk.ResponseType.OK:
                return
            text = self.value_entry.get_text().strip()
            if not text:
                self.set_status("Operation cancelled")
                return
            self._run(text)
        finally:
            self.dialog.destroy()

    def _run(self, text: str) -> None:
        try:
            result = self.perform(text)
        except GLib.Error as error:
            message = error.message or str(error)
            self.set_status(message)
            self._show_error(message)
            return

        self.set_status(self.success_message)
        self.on_success(result)

    def _show_error(self, message: str) -> None:
        dialog = Gtk.Dialog.new()
        dialog.set_title(self.failure_title)
        dialog.set_transient_for(self.window)
        dialog.set_modal(True)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        label = Gtk.Label(label=message, xalign=0.0, yalign=0.0)
        label.set_wrap(True)
        dialog.get_content_area().append(label)
        dialog.response.connect(lambda dlg, *_args: cast(Gtk.Dialog, dlg).destroy())
        dialog.present()
