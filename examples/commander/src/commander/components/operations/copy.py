from __future__ import annotations

from collections.abc import Callable

from ginext import Gtk

from commander.components.location import expand_home
from commander.components.operations.base import OperationDialog
from commander.fs import File


def prompt_copy(
    window: Gtk.Window,
    *,
    source: File,
    target_dir: File,
    set_status: Callable[[str], None],
    on_success: Callable[[File], None],
) -> None:
    basename = source.basename or "copy"
    dialog = OperationDialog(
        window,
        title="Copy",
        accept_label="Copy",
        message=f"Copy {basename} to:",
        initial_value=_destination_text(target_dir, basename),
        failure_title="Copy Failed",
        success_message=f"Copied {basename}",
        set_status=set_status,
        on_success=on_success,
        perform=lambda text: source.copy_to(File.from_input(expand_home(text))),
    )
    dialog.present()


def _destination_text(directory: File, basename: str) -> str:
    child = directory.child(basename)
    return child.path or child.parse_name or child.uri
