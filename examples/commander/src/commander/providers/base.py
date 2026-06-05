from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ginext import Gio, Gtk

from commander.fs import File


class ProviderCapability(StrEnum):
    QUICK_VIEW = "quick-view"


@dataclass(frozen=True)
class CommanderProviderContext:
    capability: ProviderCapability
    app: object | None = None
    window: object | None = None


class Provider(Protocol):
    id: str
    label: str
    priority: int
    capabilities: tuple[ProviderCapability, ...]

    def supports(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> bool: ...

    def create_widget(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> Gtk.Widget: ...
