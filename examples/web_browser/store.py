"""Tiny JSON-backed history + bookmarks store.

Two flat lists, no DB. History capped to 200 entries, bookmarks unbounded.
Persisted to $XDG_STATE_HOME/goi-web-browser/{history,bookmarks}.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from goi.repository import GObject


HISTORY_MAX = 200


def _state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    d = Path(base) / "goi-web-browser"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(path: Path) -> list:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(path: Path, data) -> None:
    try:
        path.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


class Store(GObject.Object):
    """Shared history + bookmarks. Emits changed signals so windows can
    rebuild their menus / star icon."""

    # goi doesn't yet register signals declared via the `__gsignals__`
    # dict (see tests/test_gobject_gsignals_dict.py). Use the descriptor
    # form that goi already supports.
    history_changed = GObject.Signal()
    bookmarks_changed = GObject.Signal()

    def __init__(self):
        super().__init__()
        self._dir = _state_dir()
        self._history_path = self._dir / "history.json"
        self._bookmarks_path = self._dir / "bookmarks.json"
        self.history: list[dict] = _load(self._history_path)
        self.bookmarks: list[dict] = _load(self._bookmarks_path)

    # ---- history --------------------------------------------------
    def push_history(self, uri: str, title: str) -> None:
        if not uri or uri.startswith("about:"):
            return
        # Dedupe: drop any existing entry with the same URI, then prepend.
        self.history = [h for h in self.history if h.get("uri") != uri]
        self.history.insert(0, {"uri": uri, "title": title or uri})
        del self.history[HISTORY_MAX:]
        _save(self._history_path, self.history)
        self.emit("history-changed")

    def clear_history(self) -> None:
        self.history = []
        _save(self._history_path, self.history)
        self.emit("history-changed")

    # ---- bookmarks -----------------------------------------------
    def is_bookmarked(self, uri: str) -> bool:
        return any(b.get("uri") == uri for b in self.bookmarks)

    def toggle_bookmark(self, uri: str, title: str) -> bool:
        """Returns True if now bookmarked, False if removed."""
        if not uri:
            return False
        if self.is_bookmarked(uri):
            self.bookmarks = [b for b in self.bookmarks if b.get("uri") != uri]
            _save(self._bookmarks_path, self.bookmarks)
            self.emit("bookmarks-changed")
            return False
        self.bookmarks.insert(0, {"uri": uri, "title": title or uri})
        _save(self._bookmarks_path, self.bookmarks)
        self.emit("bookmarks-changed")
        return True

    def clear_bookmarks(self) -> None:
        self.bookmarks = []
        _save(self._bookmarks_path, self.bookmarks)
        self.emit("bookmarks-changed")
