from __future__ import annotations

from collections.abc import Callable

from ginext import Gtk

from commander.components.location import expand_home
from commander.components.operations.base import OperationDialog
from commander.fs import File


def prompt_move(
    window: Gtk.Window,
    *,
    source: File,
    target_dir: File,
    set_status: Callable[[str], None],
    on_success: Callable[[File], None],
) -> None:
    basename = source.basename or "item"
    dialog = OperationDialog(
        window,
        title="Move",
        accept_label="Move",
        message=f"Move {basename} to:",
        initial_value=_destination_text(target_dir, basename),
        failure_title="Move Failed",
        success_message=f"Moved {basename}",
        set_status=set_status,
        on_success=on_success,
        perform=lambda text: source.move_to(File.from_input(expand_home(text))),
    )
    dialog.present()


def _destination_text(directory: File, basename: str) -> str:
    child = directory.child(basename)
    return child.path or child.parse_name or child.uri
