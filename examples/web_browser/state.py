"""Persistent browser preferences for the WebKit example."""

from __future__ import annotations

import json
import os
from pathlib import Path

from ginext import GLib, GObject


DEFAULT_PREFS = {
    "developer-extras": True,
    "javascript": True,
    "webgl": True,
    "webrtc": True,
    "media-stream": True,
    "page-cache": True,
    "dns-prefetching": True,
    "smooth-scrolling": True,
    "tabs-to-links": True,
    "clipboard-access": True,
    "popup-windows": True,
    "print-backgrounds": True,
    "media-autoplay": True,
    "itp": True,
    "persistent-credentials": True,
    "third-party-cookies": False,
}


def _config_dir() -> Path:
    base = GLib.get_user_config_dir() or os.path.expanduser("~/.config")
    directory = Path(base) / "ginext-web-browser"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _load(path: Path) -> dict[str, bool]:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULT_PREFS)
    prefs = dict(DEFAULT_PREFS)
    prefs.update({key: value for key, value in data.items() if key in prefs})
    return prefs


def _save(path: Path, data: dict[str, bool]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(path)
    except OSError:
        pass


class BrowserState(GObject.Object, type_name="WebBrowserState"):

    developer_extras = GObject.Property(type=bool, default=True)
    javascript = GObject.Property(type=bool, default=True)
    webgl = GObject.Property(type=bool, default=True)
    webrtc = GObject.Property(type=bool, default=True)
    media_stream = GObject.Property(type=bool, default=True)
    page_cache = GObject.Property(type=bool, default=True)
    dns_prefetching = GObject.Property(type=bool, default=True)
    smooth_scrolling = GObject.Property(type=bool, default=True)
    tabs_to_links = GObject.Property(type=bool, default=True)
    clipboard_access = GObject.Property(type=bool, default=True)
    popup_windows = GObject.Property(type=bool, default=True)
    print_backgrounds = GObject.Property(type=bool, default=True)
    media_autoplay = GObject.Property(type=bool, default=True)
    itp = GObject.Property(type=bool, default=True)
    persistent_credentials = GObject.Property(type=bool, default=True)
    third_party_cookies = GObject.Property(type=bool, default=False)

    _KEYS: list[str] = list(DEFAULT_PREFS)

    def __init__(self) -> None:
        super().__init__()
        self._path = _config_dir() / "prefs.json"
        self._loading = True
        try:
            for key, value in _load(self._path).items():
                self.set_property(key, value)
        finally:
            self._loading = False
        # The new API has no all-properties "notify" connect: wire one
        # per-property notify so any change re-flushes prefs.json.
        for key in self._KEYS:
            self.notify(key).connect(self._on_notify)

    def _on_notify(self, _self: GObject.Object, _pspec: GObject.ParamSpec) -> None:
        if self._loading:
            return
        _save(self._path, {key: self.get_property(key) for key in self._KEYS})
