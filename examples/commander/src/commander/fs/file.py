from __future__ import annotations

from dataclasses import dataclass

from ginext import Gio


@dataclass(frozen=True)
class FileListing:
    file: File
    info: Gio.FileInfo


class File:
    __slots__ = ("_gio",)

    def __init__(self, file: Gio.File) -> None:
        self._gio = file

    @classmethod
    def from_gio(cls, file: Gio.File) -> File:
        return cls(file)

    @classmethod
    def from_path(cls, path: str) -> File:
        return cls(Gio.file_new_for_path(path))

    @classmethod
    def from_uri(cls, uri: str) -> File:
        return cls(Gio.file_new_for_uri(uri))

    @classmethod
    def from_input(cls, text: str) -> File:
        return cls.from_uri(text) if "://" in text else cls.from_path(text)

    @property
    def gio(self) -> Gio.File:
        return self._gio

    @property
    def uri(self) -> str:
        return self._gio.get_uri() or ""

    @property
    def path(self) -> str | None:
        return self._gio.get_path()

    @property
    def parse_name(self) -> str:
        return self._gio.get_parse_name() or self.uri

    @property
    def basename(self) -> str:
        return self._gio.get_basename() or ""

    def child(self, name: str) -> File:
        return File(self._gio.get_child(name))

    def parent(self) -> File | None:
        parent = self._gio.get_parent()
        return None if parent is None else File(parent)

    def query_exists(self) -> bool:
        return self._gio.query_exists(None)

    def query_info(
        self,
        attributes: str,
        flags: Gio.FileQueryInfoFlags = Gio.FileQueryInfoFlags.NONE,
    ) -> Gio.FileInfo:
        return self._gio.query_info(attributes, flags, None)

    def query_filesystem_info(self, attributes: str) -> Gio.FileInfo:
        return self._gio.query_filesystem_info(attributes, None)

    def list_children(
        self,
        attributes: str,
        flags: Gio.FileQueryInfoFlags = Gio.FileQueryInfoFlags.NONE,
    ) -> list[FileListing]:
        enumerator = self._gio.enumerate_children(attributes, flags, None)
        children: list[FileListing] = []
        try:
            while True:
                info = enumerator.next_file(None)
                if info is None:
                    break
                name = info.get_name()
                if not name:
                    continue
                children.append(FileListing(self.child(name), info))
        finally:
            enumerator.close(None)
        return children

    def load_contents(self) -> bytes:
        _ok, contents, _etag = self._gio.load_contents(None)
        return bytes(contents)

    def read_stream(self) -> Gio.FileInputStream:
        return self._gio.read(None)

    def make_directory(self, *, parents: bool = False) -> None:
        if parents:
            self._gio.make_directory_with_parents(None)
            return
        self._gio.make_directory(None)

    def rename(self, display_name: str) -> File:
        return File(self._gio.set_display_name(display_name, None))

    def copy_to(
        self,
        destination: File,
        *,
        flags: Gio.FileCopyFlags = Gio.FileCopyFlags.NONE,
        recursive: bool = True,
    ) -> File:
        info = self.query_info("standard::type")
        if recursive and info.get_file_type() == Gio.FileType.DIRECTORY:
            destination.make_directory()
            for child in self.list_children("standard::name,standard::type"):
                child.file.copy_to(destination.child(child.info.get_name() or ""), flags=flags)
            return destination

        self._gio.copy(destination.gio, flags, None, None)
        return destination

    def move_to(
        self,
        destination: File,
        *,
        flags: Gio.FileCopyFlags = Gio.FileCopyFlags.NONE,
    ) -> File:
        self._gio.move(destination.gio, flags, None, None)
        return destination

    def launch_default(self) -> None:
        Gio.AppInfo.launch_default_for_uri(self.uri, None)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, File):
            return NotImplemented
        return self.uri == other.uri

    def __hash__(self) -> int:
        return hash(self.uri)

    def __str__(self) -> str:
        return self.path or self.parse_name
