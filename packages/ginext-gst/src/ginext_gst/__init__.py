# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any, Callable, TypeVar

from ginext import Gst

from .plugin import (
    PluginDesc,
    register_element,
    register_plugin,
    register_plugin_module,
)

_T = TypeVar("_T", bound=type[Any])


def metadata(
    longname: str,
    classification: str,
    description: str,
    author: str,
) -> Callable[[_T], _T]:
    def decorator(cls: _T) -> _T:
        cls.set_metadata(longname, classification, description, author)
        return cls

    return decorator


def pads(*templates: Any) -> Callable[[_T], _T]:
    def decorator(cls: _T) -> _T:
        for templ in templates:
            cls.add_pad_template(templ)
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
