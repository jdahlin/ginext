from __future__ import annotations

import sys
from collections.abc import Iterable
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from ginext import Gio, Gtk

from commander.fs import File
from commander.providers.base import (
    CommanderProviderContext,
    Provider,
    ProviderCapability,
)

__all__ = [
    "CommanderProviderContext",
    "CommanderProviderRegistry",
    "LazyEntryPointProvider",
    "Provider",
    "ProviderCapability",
]

ENTRY_POINT_GROUP = "goi_commander.providers"


class LazyEntryPointProvider:
    capabilities: tuple[ProviderCapability, ...] = (ProviderCapability.QUICK_VIEW,)
    priority = 0

    def __init__(self, entry_point: EntryPoint) -> None:
        self._entry_point = entry_point
        self._provider: Provider | None = None
        self._load_failed = False
        self.id = entry_point.name
        self.label = entry_point.name

    def supports(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> bool:
        provider = self._load_provider()
        if provider is None:
            return False
        return provider.supports(file, info, context)

    def create_widget(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> Gtk.Widget:
        provider = self._load_provider()
        if provider is None:
            message = f"Provider {self._entry_point.name!r} failed to load"
            label = Gtk.Label(label=message, xalign=0.0, yalign=0.0)
            label.set_wrap(True)
            return label
        return provider.create_widget(file, info, context)

    def _load_provider(self) -> Provider | None:
        if self._provider is not None:
            return self._provider
        if self._load_failed:
            return None

        try:
            provider_factory = self._entry_point.load()
        except ImportError as error:
            self._load_failed = True
            print(
                f"[commander] provider {self._entry_point.name!r} failed to load: {error}",
                file=sys.stderr,
            )
            return None

        self._provider = provider_factory()
        self.id = self._provider.id
        self.label = self._provider.label
        self.priority = self._provider.priority
        self.capabilities = self._provider.capabilities
        return self._provider


class CommanderProviderRegistry:
    def __init__(self) -> None:
        self._providers: list[Provider] = []

    @property
    def providers(self) -> tuple[Provider, ...]:
        return tuple(self._providers)

    def register(self, provider: Provider) -> None:
        self._providers.append(provider)
        self._providers.sort(key=lambda item: item.priority, reverse=True)

    def register_many(self, providers: Iterable[Provider]) -> None:
        for provider in providers:
            self.register(provider)

    def load_entry_points(self) -> None:
        discovered = entry_points(group=ENTRY_POINT_GROUP)
        for entry_point in discovered:
            self.register(LazyEntryPointProvider(entry_point))

    def best_for(
        self,
        capability: ProviderCapability,
        file: File,
        info: Gio.FileInfo,
        *,
        app: Any = None,
        window: Any = None,
    ) -> Provider | None:
        context = CommanderProviderContext(
            capability=capability,
            app=app,
            window=window,
        )
        for provider in self._providers:
            if capability not in provider.capabilities:
                continue
            if provider.supports(file, info, context):
                return provider
        return None
