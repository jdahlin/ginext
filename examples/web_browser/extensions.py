"""Small WebExtension-shaped registry for the browser example.

This is intentionally modest. WebKitGTK can parse WebExtension manifests, while
content blocking is exposed through UserContentFilterStore/UserContentManager.
We use both pieces without trying to implement a complete browser extension
runtime in Python.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


_EXAMPLE_DIR = Path(__file__).resolve().parent


def _data_home() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "goi-web-browser"


def _cache_home() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "goi-web-browser"


@dataclass(frozen=True)
class ExtensionInfo:
    path: Path
    name: str
    version: str
    description: str
    manifest_version: int
    permissions: tuple[str, ...]
    optional_permissions: tuple[str, ...]
    content_filters: tuple[Path, ...]
    has_background: bool
    has_content_scripts: bool
    has_declarative_rules: bool
    enabled: bool = True

    @property
    def display_name(self) -> str:
        return self.name or self.path.name


def _as_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str))


def _manifest_text(manifest: dict[str, Any], key: str) -> str:
    value = manifest.get(key)
    return value if isinstance(value, str) else ""


def _find_content_filters(path: Path, manifest: dict[str, Any]) -> tuple[Path, ...]:
    filters: list[Path] = []
    for rel in ("content-filters", "filters"):
        directory = path / rel
        if directory.is_dir():
            filters.extend(sorted(directory.glob("*.json")))

    browser_specific = manifest.get("browser_specific_settings")
    if isinstance(browser_specific, dict):
        goi = browser_specific.get("goi")
        if isinstance(goi, dict):
            for rel in _as_tuple(goi.get("content_filters")):
                candidate = path / rel
                if candidate.is_file():
                    filters.append(candidate)

    seen: set[Path] = set()
    unique: list[Path] = []
    for item in filters:
        resolved = item.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(item)
    return tuple(unique)


def read_extension(path: Path) -> ExtensionInfo | None:
    manifest_path = path / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(manifest, dict):
        return None

    background = manifest.get("background")
    dnr = manifest.get("declarative_net_request")
    return ExtensionInfo(
        path=path,
        name=_manifest_text(manifest, "name"),
        version=_manifest_text(manifest, "version"),
        description=_manifest_text(manifest, "description"),
        manifest_version=int(manifest.get("manifest_version") or 0),
        permissions=_as_tuple(manifest.get("permissions")),
        optional_permissions=_as_tuple(manifest.get("optional_permissions")),
        content_filters=_find_content_filters(path, manifest),
        has_background=bool(background),
        has_content_scripts=bool(manifest.get("content_scripts")),
        has_declarative_rules=bool(dnr),
    )


class ExtensionRegistry:
    """Discovers extension folders and owns compiled content filters."""

    def __init__(self) -> None:
        self.extension_dirs = (
            _EXAMPLE_DIR / "extensions",
            _data_home() / "extensions",
        )
        self.filter_store_path = _cache_home() / "content-filters"
        self.filter_store_path.mkdir(parents=True, exist_ok=True)
        self.extensions: list[ExtensionInfo] = []
        self._filters: list[Any] = []
        self._content_managers: list[Any] = []
        self._filter_store = None
        self._WebKit = None
        self._Gio = None

    def discover(self) -> list[ExtensionInfo]:
        found: list[ExtensionInfo] = []
        for directory in self.extension_dirs:
            if not directory.is_dir():
                continue
            for child in sorted(directory.iterdir()):
                if not child.is_dir():
                    continue
                info = read_extension(child)
                if info is not None:
                    found.append(info)
        self.extensions = found
        return found

    def start(self, WebKit: Any, Gio: Any) -> None:
        self._WebKit = WebKit
        self._Gio = Gio
        self.discover()
        store_type = getattr(WebKit, "UserContentFilterStore", None)
        if store_type is None:
            return
        self._filter_store = store_type.new(str(self.filter_store_path))
        for info in self.extensions:
            if not info.enabled:
                continue
            for source in info.content_filters:
                self._save_filter(info, source)

    def create_user_content_manager(self) -> Any:
        WebKit = self._WebKit
        if WebKit is None or not hasattr(WebKit, "UserContentManager"):
            return None
        manager = WebKit.UserContentManager.new()
        self._content_managers.append(manager)
        for content_filter in self._filters:
            manager.add_filter(content_filter)
        return manager

    def summary(self) -> str:
        if not self.extensions:
            return "No extensions found"
        lines = []
        for info in self.extensions:
            capabilities = []
            if info.content_filters:
                capabilities.append(f"{len(info.content_filters)} content filter(s)")
            if info.has_content_scripts:
                capabilities.append("content scripts")
            if info.has_background:
                capabilities.append("background")
            if info.has_declarative_rules:
                capabilities.append("declarative rules")
            suffix = ", ".join(capabilities) if capabilities else "metadata only"
            lines.append(f"{info.display_name} {info.version}: {suffix}")
        return "\n".join(lines)

    def _save_filter(self, info: ExtensionInfo, source: Path) -> None:
        if self._filter_store is None or self._Gio is None:
            return
        identifier = self._filter_identifier(info, source)
        file = self._Gio.File.new_for_path(str(source))
        try:
            self._filter_store.save_from_file(
                identifier, file, None, self._on_filter_saved
            )
        except Exception as exc:  # noqa: BLE001
            print(
                f"[web-browser] failed to start content filter compile: {exc}",
                file=sys.stderr,
            )

    def _on_filter_saved(self, store: Any, result: Any) -> None:
        try:
            content_filter = store.save_finish(result)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[web-browser] failed to compile content filter: {exc}",
                file=sys.stderr,
            )
            return
        self._filters.append(content_filter)
        for manager in list(self._content_managers):
            try:
                manager.add_filter(content_filter)
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[web-browser] failed to attach content filter: {exc}",
                    file=sys.stderr,
                )

    @staticmethod
    def _filter_identifier(info: ExtensionInfo, source: Path) -> str:
        digest = hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest()[:12]
        return f"{info.path.name}-{source.stem}-{digest}"
