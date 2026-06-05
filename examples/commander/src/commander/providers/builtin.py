from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any

from ginext import Gio

from commander.fs import File
from commander.providers.base import (
    CommanderProviderContext,
    Provider,
    ProviderCapability,
)

TEXT_CONTENT_PREFIX = "text/"
SOURCE_CONTENT_TYPES = (
    "application/javascript",
    "application/json",
    "application/x-python-code",
    "application/xml",
)


class LazyProvider:
    capabilities: tuple[ProviderCapability, ...] = (ProviderCapability.QUICK_VIEW,)

    def __init__(
        self,
        *,
        id: str,
        label: str,
        priority: int,
        factory_path: str,
        supports_content_type: Callable[[str], bool],
    ) -> None:
        self.id = id
        self.label = label
        self.priority = priority
        self.factory_path = factory_path
        self._supports_content_type = supports_content_type
        self._provider: Provider | None = None

    def supports(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> bool:
        content_type = info.get_content_type() or ""
        return self._supports_content_type(content_type)

    def create_widget(
        self,
        file: File,
        info: Gio.FileInfo,
        context: CommanderProviderContext,
    ) -> Any:
        return self._load_provider().create_widget(file, info, context)

    def _load_provider(self) -> Provider:
        if self._provider is None:
            module_name, class_name = self.factory_path.rsplit(".", 1)
            module = import_module(module_name)
            self._provider = getattr(module, class_name)()
        return self._provider


def _is_text_content_type(content_type: str) -> bool:
    if content_type.startswith(TEXT_CONTENT_PREFIX):
        return True

    return any(Gio.content_type_is_mime_type(content_type, item) for item in SOURCE_CONTENT_TYPES)


def _is_pdf_content_type(content_type: str) -> bool:
    return Gio.content_type_is_mime_type(content_type, "application/pdf")


def _has_prefix(*prefixes: str) -> Callable[[str], bool]:
    return lambda content_type: content_type.startswith(prefixes)


def builtin_providers() -> tuple[LazyProvider, ...]:
    return (
        LazyProvider(
            id="text",
            label="Text",
            priority=100,
            factory_path="commander.providers.text.TextProvider",
            supports_content_type=_is_text_content_type,
        ),
        LazyProvider(
            id="image",
            label="Image",
            priority=90,
            factory_path="commander.providers.image.ImageProvider",
            supports_content_type=_has_prefix("image/"),
        ),
        LazyProvider(
            id="pdf",
            label="PDF",
            priority=80,
            factory_path="commander.providers.pdf.PdfProvider",
            supports_content_type=_is_pdf_content_type,
        ),
        LazyProvider(
            id="video",
            label="Video",
            priority=70,
            factory_path="commander.providers.video.VideoProvider",
            supports_content_type=_has_prefix("video/", "audio/"),
        ),
    )
