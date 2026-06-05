from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ginext import GLib

DEFAULT_STATE = {
    "left-location": Path.home().as_uri(),
    "right-location": Path.home().as_uri(),
    "show-hidden-files": False,
    "style-level": 2,
}
DEFAULT_STYLE_LEVEL = 2

STYLE_LEVEL_MIN = 0
STYLE_LEVEL_MAX = 4
STYLE_LEVELS = (
    "Compact",
    "Dense",
    "Balanced",
    "Comfortable",
    "Normal",
)


def _config_dir() -> Path:
    base = GLib.get_user_config_dir() or os.path.expanduser("~/.config")
    directory = Path(base) / "goi-commander"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _load(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError) as error:
        if not isinstance(error, FileNotFoundError):
            print(f"[commander] settings load from {path} failed: {error}", file=sys.stderr)
        return dict(DEFAULT_STATE)

    state = dict(DEFAULT_STATE)
    state.update({key: value for key, value in data.items() if key in state})
    return state


def _save(path: Path, data: dict[str, object]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(path)
    except OSError as error:
        print(f"[commander] settings save to {path} failed: {error}", file=sys.stderr)


class CommanderSettings:
    def __init__(self) -> None:
        self._path = _config_dir() / "state.json"
        self._state = _load(self._path)

    def location_uri(self, side: str) -> str:
        return str(self._state.get(f"{side}-location") or DEFAULT_STATE[f"{side}-location"])

    def set_location_uri(self, side: str, uri: str) -> None:
        if side not in ("left", "right") or not uri:
            return
        key = f"{side}-location"
        if self._state.get(key) == uri:
            return
        self._state[key] = uri
        _save(self._path, self._state)

    @property
    def show_hidden_files(self) -> bool:
        return bool(self._state.get("show-hidden-files"))

    def set_show_hidden_files(self, enabled: bool) -> None:
        value = bool(enabled)
        if self._state.get("show-hidden-files") == value:
            return
        self._state["show-hidden-files"] = value
        _save(self._path, self._state)

    @property
    def style_level(self) -> int:
        value = self._state.get("style-level")
        if isinstance(value, int):
            return max(STYLE_LEVEL_MIN, min(STYLE_LEVEL_MAX, value))
        return DEFAULT_STYLE_LEVEL

    def set_style_level(self, level: int) -> None:
        value = max(STYLE_LEVEL_MIN, min(STYLE_LEVEL_MAX, int(level)))
        if self._state.get("style-level") == value:
            return
        self._state["style-level"] = value
        _save(self._path, self._state)
