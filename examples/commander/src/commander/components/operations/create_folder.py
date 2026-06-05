from __future__ import annotations

from collections.abc import Callable

from ginext import Gtk

from commander.components.operations.base import OperationDialog
from commander.fs import File


def prompt_create_folder(
    window: Gtk.Window,
    *,
    parent_dir: File,
    set_status: Callable[[str], None],
    on_success: Callable[[File], None],
) -> None:
    dialog = OperationDialog(
        window,
        title="New Folder",
        accept_label="Create",
        message="Folder name:",
        initial_value="New folder",
        failure_title="New Folder Failed",
        success_message="Created folder",
        set_status=set_status,
        on_success=on_success,
        perform=lambda text: _create_folder(parent_dir, text),
    )
    dialog.present()


def _create_folder(parent_dir: File, name: str) -> File:
    created = parent_dir.child(name)
    created.make_directory()
    return created
