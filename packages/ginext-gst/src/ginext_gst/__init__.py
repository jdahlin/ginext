# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar

from ginext import Gst

from .plugin import (
    PluginDesc,
    register_element,
    register_plugin,
    register_plugin_module,
)

_T = TypeVar("_T", bound=type[Any])


class _HasMetadata(Protocol):
    @classmethod
    def set_metadata(
        cls, longname: str, classification: str, description: str, author: str
    ) -> None: ...


class _HasPadTemplates(Protocol):
    @classmethod
    def add_pad_template(cls, templ: Any) -> None: ...


def metadata(
    longname: str,
    classification: str,
    description: str,
    author: str,
) -> Callable[[_T], _T]:
    def decorator(cls: _T) -> _T:
        metadata_cls: _HasMetadata = cls
        metadata_cls.set_metadata(longname, classification, description, author)
        return cls

    return decorator


def pads(*templates: Any) -> Callable[[_T], _T]:
    def decorator(cls: _T) -> _T:
        pad_cls: _HasPadTemplates = cls
        for templ in templates:
            pad_cls.add_pad_template(templ)
        return cls

    return decorator


def element(name: str, *, rank: Any = None) -> Callable[[_T], _T]:
    def decorator(cls: _T) -> _T:
        Gst.Element.register(None, name, Gst.Rank.NONE if rank is None else rank, cls)
        return cls

    return decorator


__all__ = [
    "PluginDesc",
    "element",
    "metadata",
    "pads",
    "register_element",
    "register_plugin",
    "register_plugin_module",
]
