"""Document — a GtkSource.Buffer wrapped with file-state metadata.

Each open document has a Document; tabs reference the document and
two tabs can't share one in this showcase (gnome-text-editor allows
multi-window views of the same buffer; we don't). The Document owns
the buffer, an optional on-disk Gio.File, the language detected by
GtkSource.LanguageManager, and a "modified" flag derived from the
buffer.

File I/O goes through Gio.File. load_contents returns a tuple; on
failure it raises GLib.Error, so a returned tuple implies success.
"""

from __future__ import annotations

import sys

from ginext import GLib, GObject, Gio, GtkSource


_DRAFT_SEQ = 0


def _next_draft_title() -> str:
    global _DRAFT_SEQ
    _DRAFT_SEQ += 1
    return f"Draft {_DRAFT_SEQ}" if _DRAFT_SEQ > 1 else "Draft"


class Document(GObject.Object, type_name="PyeditDocument"):

    title = GObject.Property(type=str, default="")
    subtitle = GObject.Property(type=str, default="")
    modified = GObject.Property(type=bool, default=False)
    has_file = GObject.Property(type=bool, default=False)

    def __init__(self, file: Gio.File | None = None) -> None:
        super().__init__()
        self._lang_mgr = GtkSource.LanguageManager.get_default()
        self.buffer = GtkSource.Buffer.new(None)
        self.buffer.set_highlight_matching_brackets(True)
        self.buffer.set_highlight_syntax(True)
        self.buffer.modified_changed.connect(self._on_modified_changed)
        self.file: Gio.File | None = None
        if file is None:
            self.title = _next_draft_title()
            self.subtitle = ""
        else:
            self.load_from_file(file)

    # --- factory helpers ---------------------------------------------
    @classmethod
    def from_path(cls, path: str) -> Document:
        return cls(Gio.file_new_for_path(path))

    @classmethod
    def from_uri(cls, uri: str) -> Document:
        return cls(Gio.file_new_for_uri(uri))

    # --- file ops -----------------------------------------------------
    def load_from_file(self, file: Gio.File) -> None:
        """Replace buffer contents with the file's. Best-effort utf-8.

        `load_contents` returns `(ok, contents, etag)` (pygobject shape).
        Failure raises GLib.Error, so a returned tuple implies ok=True
        — we just unpack the bytes."""
        try:
            _ok, contents, _etag = file.load_contents(None)
        except GLib.Error as e:
            print(
                f"[pyedit] load_contents({file.get_uri()}) failed: "
                f"{e.domain}/{e.code}: {e.message}",
                file=sys.stderr,
            )
            return
        text = bytes(contents).decode("utf-8", errors="replace")

        self.file = file
        self.has_file = True
        self.buffer.begin_irreversible_action()
        try:
            self.buffer.set_text(text, -1)
        finally:
            self.buffer.end_irreversible_action()
        self.buffer.set_modified(False)
        self._refresh_titles()
        self._refresh_language()

    def save_to_file(self, file: Gio.File | None = None) -> bool:
        target = file or self.file
        if target is None:
            return False
        start, end = self.buffer.get_bounds()
        text = self.buffer.get_text(start, end, True)
        data = text.encode("utf-8")
        # Gio.File.replace_contents accepts bytes for the data arg now
        # (marshal/string.c accepts str/bytes/bytearray).
        try:
            target.replace_contents(
                data,
                None,  # etag
                False,  # make_backup
                Gio.FileCreateFlags.NONE,
                None,  # cancellable
            )
        except GLib.Error as e:
            print(
                f"[pyedit] save failed for {target.get_uri()}: "
                f"{e.domain}/{e.code}: {e.message}",
                file=sys.stderr,
            )
            return False
        self.file = target
        self.has_file = True
        self.buffer.set_modified(False)
        self._refresh_titles()
        self._refresh_language()
        return True

    # --- queries ------------------------------------------------------
    # Gio.File.get_{uri,path,basename,parent} are pure accessors — they
    # never raise GLib.Error, so no try/except is needed.
    @property
    def uri(self) -> str:
        return self.file.get_uri() or "" if self.file is not None else ""

    @property
    def path(self) -> str:
        return self.file.get_path() or "" if self.file is not None else ""

    @property
    def display_name(self) -> str:
        if self.file is None:
            return self.title or "Draft"
        return self.file.get_basename() or self.uri

    # --- updates ------------------------------------------------------
    def _refresh_titles(self) -> None:
        if self.file is None:
            return
        self.title = self.file.get_basename() or "Untitled"
        parent = self.file.get_parent()
        self.subtitle = parent.get_parse_name() if parent is not None else ""

    def _refresh_language(self) -> None:
        if self.file is None:
            return
        # GtkSourceLanguageManager.guess_language wants content_type but
        # accepts a filename hint alone for most files.
        name = self.file.get_basename() or ""
        lang = self._lang_mgr.guess_language(name, None)
        self.buffer.set_language(lang)

    def _on_modified_changed(self, _buf: GtkSource.Buffer) -> None:
        self.modified = self.buffer.get_modified()
