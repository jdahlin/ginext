from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ginext import Gio, GLib

from commander.fs import File


@dataclass(frozen=True)
class LocationChoice:
    label: str
    file: File
    kind: str

    @property
    def uri(self) -> str:
        return self.file.uri


def _append_unique(choices: list[LocationChoice], choice: LocationChoice) -> None:
    uri = choice.uri
    if not uri:
        return
    if any(existing.uri == uri for existing in choices):
        return
    choices.append(choice)


def _mount_file(mount: Gio.Mount) -> File | None:
    for method in ("get_root", "get_default_location"):
        if hasattr(mount, method):
            try:
                file_ = getattr(mount, method)()
            except GLib.Error:
                continue
            if file_ is not None:
                return File.from_gio(file_)
    return None


def _volume_file(volume: Gio.Volume) -> File | None:
    mount = volume.get_mount()
    if mount is not None:
        return _mount_file(mount)
    if hasattr(volume, "get_activation_root"):
        try:
            root = volume.get_activation_root()
        except GLib.Error:
            return None
        return None if root is None else File.from_gio(root)
    return None


def list_location_choices() -> list[LocationChoice]:
    choices: list[LocationChoice] = [
        LocationChoice("Home", File.from_path(str(Path.home())), "home"),
        LocationChoice("Root", File.from_path("/"), "root"),
        LocationChoice("Network", File.from_uri("network:///"), "network"),
    ]

    monitor = Gio.VolumeMonitor.get()
    for mount in monitor.get_mounts():
        file_ = _mount_file(mount)
        if file_ is None:
            continue
        _append_unique(choices, LocationChoice(mount.get_name(), file_, "mount"))

    for volume in monitor.get_volumes():
        file_ = _volume_file(volume)
        if file_ is None:
            continue
        _append_unique(choices, LocationChoice(volume.get_name(), file_, "volume"))

    return choices


def choose_location_index(choices: list[LocationChoice], current: File) -> int:
    current_uri = current.uri
    if not current_uri:
        return 0

    best_index = 0
    best_len = -1
    for index, choice in enumerate(choices):
        uri = choice.uri
        if not uri:
            continue
        if current_uri == uri or current_uri.startswith(uri.rstrip("/") + "/"):
            if len(uri) > best_len:
                best_index = index
                best_len = len(uri)
    return best_index
