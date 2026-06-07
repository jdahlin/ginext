"""JSON-backed persistent state for the terminal app.

`prefs.json` carries user-tweakable preferences (font, palette, scrollback,
opacity, cursor shape, bell, allow-bold). `state.json` carries window
geometry. Properties are GObject so the prefs UI can bind to them; on
notify we re-flush and re-apply to every open Vte.Terminal.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ginext import GLib, GObject


DEFAULT_PREFS: dict[str, object] = {
    "font": "Monospace 11",
    "use-system-font": False,
    "palette": "Tango",
    "scrollback-lines": 10000,
    "opacity": 1.0,
    "cursor-shape": "block",  # block | ibeam | underline
    "audible-bell": False,
    "allow-bold": True,
    "scroll-on-output": False,
    "scroll-on-keystroke": True,
}

DEFAULT_STATE: dict[str, object] = {
    "window-width": 900,
    "window-height": 600,
    "window-maximized": False,
}


def _config_dir() -> Path:
    base = GLib.get_user_config_dir() or os.path.expanduser("~/.config")
    d = Path(base) / "ginext-terminal"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(path: Path, defaults: dict[str, object]) -> dict[str, object]:
    if not path.exists():
        return dict(defaults)
    try:
        with path.open() as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"[terminal] state load from {path!r} failed: {e}; using defaults",
            file=sys.stderr,
        )
        return dict(defaults)
    out = dict(defaults)
    out.update({k: v for k, v in data.items() if k in defaults})
    return out


def _save(path: Path, data: dict[str, object]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(path)
    except OSError as e:
        print(f"[terminal] state save to {path!r} failed: {e}", file=sys.stderr)


class State(GObject.Object, type_name="TerminalState"):
    """Single source of truth for prefs + window state."""

    # --- prefs --------------------------------------------------------
    font = GObject.Property(type=str, default="Monospace 11")
    use_system_font = GObject.Property(type=bool, default=False)
    palette = GObject.Property(type=str, default="Tango")
    scrollback_lines = GObject.Property(type=int, default=10000)
    opacity = GObject.Property(type=float, default=1.0)
    cursor_shape = GObject.Property(type=str, default="block")
    audible_bell = GObject.Property(type=bool, default=False)
    allow_bold = GObject.Property(type=bool, default=True)
    scroll_on_output = GObject.Property(type=bool, default=False)
    scroll_on_keystroke = GObject.Property(type=bool, default=True)

    # --- window state -------------------------------------------------
    window_width = GObject.Property(type=int, default=900)
    window_height = GObject.Property(type=int, default=600)
    window_maximized = GObject.Property(type=bool, default=False)

    _PREFS_KEYS: list[str] = list(DEFAULT_PREFS.keys())
    _STATE_KEYS: list[str] = ["window-width", "window-height", "window-maximized"]

    def __init__(self) -> None:
        super().__init__()
        self._dir = _config_dir()
        self._prefs_path = self._dir / "prefs.json"
        self._state_path = self._dir / "state.json"
        self._loading = True
        try:
            self._load()
        finally:
            self._loading = False
        # Per-property notify (the new API has no all-properties "notify"
        # connect): flush prefs/state whenever the matching group changes.
        for k in self._PREFS_KEYS:
            self.notify(k).connect(self._on_pref_notify)
        for k in self._STATE_KEYS:
            self.notify(k).connect(self._on_state_notify)

    def _load(self) -> None:
        prefs = _load(self._prefs_path, DEFAULT_PREFS)
        for k in self._PREFS_KEYS:
            self.set_property(k, prefs.get(k, DEFAULT_PREFS[k]))
        state = _load(self._state_path, DEFAULT_STATE)
        for k in self._STATE_KEYS:
            self.set_property(k, state.get(k, DEFAULT_STATE[k]))

    def _flush_prefs(self) -> None:
        _save(self._prefs_path, {k: self.get_property(k) for k in self._PREFS_KEYS})

    def _flush_state(self) -> None:
        _save(self._state_path, {k: self.get_property(k) for k in self._STATE_KEYS})

    def _on_pref_notify(self, _self: GObject.Object, _pspec: GObject.ParamSpec) -> None:
        if not self._loading:
            self._flush_prefs()

    def _on_state_notify(self, _self: GObject.Object, _pspec: GObject.ParamSpec) -> None:
        if not self._loading:
            self._flush_state()
