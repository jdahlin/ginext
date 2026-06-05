from __future__ import annotations

from collections.abc import Callable

from ginext import Gtk

from commander.components.operations.base import OperationDialog
from commander.fs import File


def prompt_rename(
    window: Gtk.Window,
    *,
    source: File,
    set_status: Callable[[str], None],
    on_success: Callable[[File], None],
) -> None:
    basename = source.basename or "item"
    dialog = OperationDialog(
        window,
        title="Rename",
        accept_label="Rename",
        message="New name:",
        initial_value=basename,
        failure_title="Rename Failed",
        success_message=f"Renamed {basename}",
        set_status=set_status,
        on_success=on_success,
        perform=source.rename,
    )
    dialog.present()
