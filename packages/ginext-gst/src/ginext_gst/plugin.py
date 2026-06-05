# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import ginext

Gst = ginext.Gst


@dataclass(frozen=True, slots=True)
class PluginDesc:
    name: str
    description: str
    version: str
    license: str
    source: str
    package: str
    origin: str
    elements: tuple[type[Any], ...]
    major_version: int | None = None
    minor_version: int | None = None


def gst_extension_bucket(cls: type[Any]) -> dict[str, Any]:
    try:
        bucket = cls.gimeta.extensions["Gst"]
    except (AttributeError, KeyError) as exc:
        raise TypeError(f"{cls.__name__} has no Gst authoring metadata") from exc
    if not isinstance(bucket, dict):
        raise TypeError(f"{cls.__name__} Gst authoring metadata is not a dict")
    return bucket


def plugin_desc_from_module(module: Any) -> PluginDesc:
    try:
        desc = module.PLUGIN
    except AttributeError:
        desc = None
    if isinstance(desc, PluginDesc):
        return desc
    raise TypeError(f"{module.__name__} does not define a PluginDesc as PLUGIN")


def register_element(plugin: Any, cls: type[Any]) -> bool:
    if not issubclass(cls, Gst.Element):
        raise TypeError(f"{cls.__name__} is not a Gst.Element subclass")

    bucket = gst_extension_bucket(cls)
    metadata = bucket.get("element_metadata")
    if not isinstance(metadata, dict) or not metadata:
        raise TypeError(f"{cls.__name__} is missing Gst element metadata")
    pad_templates = bucket.get("pad_templates")
    if not isinstance(pad_templates, list) or not pad_templates:
        raise TypeError(f"{cls.__name__} is missing Gst pad templates")
    registrations = bucket.get("registrations")
    if not isinstance(registrations, list) or not registrations:
        raise TypeError(f"{cls.__name__} has no Gst registration info")

    registration = registrations[-1]
    name = registration.get("name")
    rank = registration.get("rank")
    if not isinstance(name, str) or not name:
        raise TypeError(f"{cls.__name__} registration is missing element name")
    return bool(Gst.Element.register(plugin, name, rank, cls))


def validate_plugin_desc(desc: PluginDesc) -> None:
    for cls in desc.elements:
        if not issubclass(cls, Gst.Element):
            raise TypeError(f"{cls.__name__} is not a Gst.Element subclass")
        bucket = gst_extension_bucket(cls)
        metadata = bucket.get("element_metadata")
        if not isinstance(metadata, dict) or not metadata:
            raise TypeError(f"{cls.__name__} is missing Gst element metadata")
        pad_templates = bucket.get("pad_templates")
        if not isinstance(pad_templates, list) or not pad_templates:
            raise TypeError(f"{cls.__name__} is missing Gst pad templates")
        registrations = bucket.get("registrations")
        if not isinstance(registrations, list) or not registrations:
            raise TypeError(f"{cls.__name__} has no Gst registration info")


def register_plugin(desc: PluginDesc) -> bool:
    validate_plugin_desc(desc)
    major = Gst.VERSION_MAJOR if desc.major_version is None else desc.major_version
    minor = Gst.VERSION_MINOR if desc.minor_version is None else desc.minor_version

    def plugin_init(plugin: Any) -> bool:
        return all(register_element(plugin, cls) for cls in desc.elements)

    return bool(
        Gst.Plugin.register_static(
            major,
            minor,
            desc.name,
            desc.description,
            plugin_init,
            desc.version,
            desc.license,
            desc.source,
            desc.package,
            desc.origin,
        )
    )


def register_plugin_module(module: Any) -> bool:
    return register_plugin(plugin_desc_from_module(module))
