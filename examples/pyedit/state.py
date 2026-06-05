"""JSON-backed persistent state in $XDG_CONFIG_HOME/pyedit/.

Two files: `prefs.json` (user-tweakable editor preferences) and
`state.json` (window geometry, recent files). Kept separate so a
"reset prefs" action can wipe one without losing the other.

`State` is a small GObject so other components can subscribe via
`notify::<prop>` to react to changes (e.g. the editor view refits
its font when prefs.font changes).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from goi.repository import GLib, GObject


DEFAULT_PREFS = {
    "font": "Monospace 11",
    "use-system-font": True,
    "tab-width": 4,
    "insert-spaces": True,
    "show-line-numbers": True,
    "highlight-current-line": True,
    "show-right-margin": False,
    "right-margin-position": 80,
    "wrap-text": True,
    "auto-indent": True,
    "show-map": False,
    "show-grid": False,
    "style-scheme": "Adwaita",
    "restore-session": True,
}

DEFAULT_STATE = {
    "window-width": 900,
    "window-height": 700,
    "window-maximized": False,
    "recent-files": [],  # list[str] of URI strings, newest first
    "recent-limit": 20,
}


def _config_dir() -> Path:
    base = GLib.get_user_config_dir() or os.path.expanduser("~/.config")
    d = Path(base) / "pyedit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(path: Path, defaults: dict) -> dict:
    import sys

    if not path.exists():
        return dict(defaults)
    try:
        with path.open() as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"[pyedit] state load from {path!r} failed: {e}; using defaults",
            file=sys.stderr,
        )
        return dict(defaults)
    # Merge so newly-added keys pick up defaults across upgrades.
    out = dict(defaults)
    out.update({k: v for k, v in data.items() if k in defaults})
    return out


def _save(path: Path, data: dict) -> None:
    import sys

    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(path)
    except OSError as e:
        print(f"[pyedit] state save to {path!r} failed: {e}", file=sys.stderr)


class State(GObject.Object):
    """Single source of truth for prefs + window state.

    Properties are declared via `GObject.Property` so the UI can bind
    against them with `bind_property` and listen with `notify::`. The
    backing store is JSON; writes flush on each set."""

    __gtype_name__ = "PyeditState"

    # --- prefs --------------------------------------------------------
    font = GObject.Property(type=str, default=DEFAULT_PREFS["font"])
    use_system_font = GObject.Property(type=bool, default=True)
    tab_width = GObject.Property(type=int, default=4)
    insert_spaces = GObject.Property(type=bool, default=True)
    show_line_numbers = GObject.Property(type=bool, default=True)
    highlight_current_line = GObject.Property(type=bool, default=True)
    show_right_margin = GObject.Property(type=bool, default=False)
    right_margin_position = GObject.Property(type=int, default=80)
    wrap_text = GObject.Property(type=bool, default=True)
    auto_indent = GObject.Property(type=bool, default=True)
    show_map = GObject.Property(type=bool, default=False)
    show_grid = GObject.Property(type=bool, default=False)
    style_scheme = GObject.Property(type=str, default="Adwaita")
    restore_session = GObject.Property(type=bool, default=True)

    # --- window state -------------------------------------------------
    window_width = GObject.Property(type=int, default=900)
    window_height = GObject.Property(type=int, default=700)
    window_maximized = GObject.Property(type=bool, default=False)

    _PREFS_KEYS = list(DEFAULT_PREFS.keys())
    _STATE_KEYS = ["window-width", "window-height", "window-maximized"]

    def __init__(self):
        super().__init__()
        self._dir = _config_dir()
        self._prefs_path = self._dir / "prefs.json"
        self._state_path = self._dir / "state.json"
        self._recent_files: list[str] = []
        self._recent_limit = DEFAULT_STATE["recent-limit"]
        self._loading = True
        try:
            self._load()
        finally:
            self._loading = False
        # Persist on every property mutation. notify fires post-set,
        # so by the time we're here `get_property` reads the new value.
        self.connect("notify", self._on_notify)

    # --- key/property name translation --------------------------------
    @staticmethod
    def _key_to_attr(key: str) -> str:
        return key.replace("-", "_")

    @staticmethod
    def _attr_to_key(attr: str) -> str:
        return attr.replace("_", "-")

    # --- I/O ----------------------------------------------------------
    def _load(self) -> None:
        prefs = _load(self._prefs_path, DEFAULT_PREFS)
        for k in self._PREFS_KEYS:
            self.set_property(k, prefs.get(k, DEFAULT_PREFS[k]))
        state = _load(self._state_path, DEFAULT_STATE)
        for k in self._STATE_KEYS:
            self.set_property(k, state.get(k, DEFAULT_STATE[k]))
        recents = state.get("recent-files", [])
        if isinstance(recents, list):
            self._recent_files = [str(u) for u in recents][: self._recent_limit]

    def _flush_prefs(self) -> None:
        _save(self._prefs_path, {k: self.get_property(k) for k in self._PREFS_KEYS})

    def _flush_state(self) -> None:
        out = {k: self.get_property(k) for k in self._STATE_KEYS}
        out["recent-files"] = list(self._recent_files)
        _save(self._state_path, out)

    def _on_notify(self, _self, pspec):
        if self._loading:
            return
        key = pspec.name
        if key in self._PREFS_KEYS:
            self._flush_prefs()
        elif key in self._STATE_KEYS:
            self._flush_state()

    # --- recent files -------------------------------------------------
    @property
    def recent_files(self) -> list[str]:
        return list(self._recent_files)

    def push_recent(self, uri: str) -> None:
        if not uri:
            return
        # Move to front, dedupe, trim.
        if uri in self._recent_files:
            self._recent_files.remove(uri)
        self._recent_files.insert(0, uri)
        del self._recent_files[self._recent_limit :]
        self._flush_state()
        self.emit("recent-files-changed")

    def clear_recents(self) -> None:
        self._recent_files.clear()
        self._flush_state()
        self.emit("recent-files-changed")

    # Class-attribute form (goi's GObject.Signal is a descriptor, not a
    # decorator factory). Emit via `self.emit("recent-files-changed")`.
    recent_files_changed = GObject.Signal()
