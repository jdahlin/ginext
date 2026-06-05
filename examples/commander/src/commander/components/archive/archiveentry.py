from __future__ import annotations

import gzip
import tempfile
from collections.abc import Callable
from urllib.parse import quote, unquote

from ginext import Gio, GLib

from commander.fs import File

ARCHIVE_INFO_ATTRIBUTES = ",".join(
    (
        "standard::content-type",
        "standard::type",
    )
)

SUPPORTED_ARCHIVE_MIME_TYPES = (
    "application/zip",
    "application/x-zip",
    "application/x-tar",
    "application/x-compressed-tar",
)


def _archive_mount_uri(file_: File) -> str:
    return "archive://" + quote(file_.uri, safe="")


def _archive_root_uri(file_: File) -> str:
    return "archive://" + quote(quote(file_.uri, safe=""), safe="") + "/"


def archive_file_for_root(root: File) -> File | None:
    uri = root.uri
    if not uri.startswith("archive://"):
        return None

    if not (encoded := uri.removeprefix("archive://").rstrip("/")):
        return None

    if not (archive_uri := unquote(unquote(encoded))):
        return None
    return File.from_uri(archive_uri)


def _is_supported_archive(file_: File) -> bool:
    try:
        info = file_.query_info(
            ARCHIVE_INFO_ATTRIBUTES,
            Gio.FileQueryInfoFlags.NONE,
        )
    except GLib.Error:
        return False

    if info.get_file_type() != Gio.FileType.REGULAR:
        return False

    if not (content_type := info.get_content_type()):
        return False
    return any(
        Gio.content_type_is_mime_type(content_type, mime) for mime in SUPPORTED_ARCHIVE_MIME_TYPES
    )


def is_plain_gzip(file_: File) -> bool:
    name = file_.basename.casefold()
    if name.endswith((".tar.gz", ".tgz")):
        return False
    try:
        info = file_.query_info(
            ARCHIVE_INFO_ATTRIBUTES,
            Gio.FileQueryInfoFlags.NONE,
        )
    except GLib.Error:
        return False
    if info.get_file_type() != Gio.FileType.REGULAR:
        return False
    content_type = info.get_content_type() or ""
    return name.endswith(".gz") or Gio.content_type_is_mime_type(content_type, "application/gzip")


def gzip_member_name(file_: File) -> str:
    name = file_.basename or "content.gz"
    return name[:-3] if name.casefold().endswith(".gz") and len(name) > 3 else "content"


def extract_gzip_member(file_: File) -> tuple[tempfile.TemporaryDirectory[str], File]:
    data = gzip.decompress(file_.load_contents())
    tempdir = tempfile.TemporaryDirectory(prefix="commander-gzip-")
    path = f"{tempdir.name}/{gzip_member_name(file_)}"
    with open(path, "wb") as out:
        out.write(data)
    return tempdir, File.from_path(path)


def _mounted_archive_root(file_: File) -> File | None:
    expected_uri = _archive_root_uri(file_)
    for mount in Gio.VolumeMonitor.get().get_mounts():
        root = mount.get_root()
        if root is not None and root.get_uri() == expected_uri:
            return File.from_gio(root)
        default_location = mount.get_default_location()
        if default_location is not None and default_location.get_uri() == expected_uri:
            return File.from_gio(default_location)
    return None


def enter_archive(
    file_: File,
    on_ready: Callable[[File], None],
    on_error: Callable[[str], None] | None = None,
) -> bool:
    if file_ is None or not _is_supported_archive(file_):
        if on_error is not None:
            on_error("Selected item is not a supported archive")
        return False

    root = _mounted_archive_root(file_)
    if root is not None:
        on_ready(root)
        return True

    archive = File.from_uri(_archive_mount_uri(file_))

    def mounted(
        archive_file: Gio.File | None,
        result: Gio.AsyncResult,
        *_args: object,
    ) -> None:
        try:
            archive.gio.mount_enclosing_volume_finish(result)
        except GLib.Error as error:
            if on_error is not None:
                on_error(f"Archive mount failed: {error}")
            return

        root = _mounted_archive_root(file_)
        if root is None:
            if on_error is not None:
                on_error("Archive mounted but no GVfs root was found")
            return
        on_ready(root)

    archive.gio.mount_enclosing_volume(
        flags=Gio.MountMountFlags.NONE,
        mount_operation=Gio.MountOperation(),
        callback=mounted,
    )
    return True
