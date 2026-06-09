# SPDX-License-Identifier: LGPL-2.1-or-later

"""Tests for Python plugin-module registration."""

from __future__ import annotations

import types

import pytest

from ginext import Gst
from ginext_gst import PluginDesc, register_plugin_module

from .support import author_request_class, author_transform_class, unique


class _PluginModule(types.ModuleType):
    PLUGIN: PluginDesc


def _make_plugin_module(plugin: PluginDesc) -> types.ModuleType:
    module = _PluginModule(unique("plugin_module"))
    module.PLUGIN = plugin
    return module


def _make_plain_element() -> type:
    type_name = unique("PlainElementType")
    return types.new_class(
        type_name,
        (Gst.Element,),
        {},
        lambda ns: ns.update({"__module__": __name__}),
    )


def test_register_plugin_module_registers_static_plugin_and_transform_factory() -> None:
    state = {
        "transform_ip": 0,
        "change_state": 0,
        "send_event": 0,
        "query": 0,
    }
    element_name = unique("py_transform").lower()
    cls = author_transform_class(
        type_name=unique("PyTransformType"),
        element_name=element_name,
        state=state,
    )
    plugin_desc = PluginDesc(
        name=unique("pyplugin"),
        description="python plugin",
        version="0.1",
        license="LGPL",
        source="ginext-gst",
        package="ginext-gst",
        origin="https://example.invalid",
        elements=(cls,),
    )
    module = _make_plugin_module(plugin_desc)

    assert register_plugin_module(module) is True

    plugin = Gst.Registry.get().find_plugin(plugin_desc.name)
    factory = Gst.ElementFactory.find(element_name)
    assert plugin is not None
    assert factory is not None
    assert factory.get_longname() == "Python Transform"


def test_plugin_module_requires_plugin_desc() -> None:
    module = types.ModuleType(unique("bad_plugin_module"))
    with pytest.raises(TypeError, match="PluginDesc"):
        register_plugin_module(module)


def test_plugin_module_requires_gst_authoring_state() -> None:
    plain_element = _make_plain_element()
    plugin_desc = PluginDesc(
        name=unique("bad_plugin"),
        description="bad plugin",
        version="0.1",
        license="LGPL",
        source="ginext-gst",
        package="ginext-gst",
        origin="https://example.invalid",
        elements=(plain_element,),
    )
    module = _make_plugin_module(plugin_desc)

    with pytest.raises(TypeError, match="has no Gst authoring metadata"):
        register_plugin_module(module)


def test_plugin_module_can_register_multiple_elements() -> None:
    transform_state = {
        "transform_ip": 0,
        "change_state": 0,
        "send_event": 0,
        "query": 0,
    }
    request_state = {
        "request_new_pad": 0,
        "release_pad": 0,
    }
    transform_name = unique("multi_transform").lower()
    request_name = unique("multi_request").lower()
    transform_cls = author_transform_class(
        type_name=unique("MultiTransformType"),
        element_name=transform_name,
        state=transform_state,
    )
    request_cls = author_request_class(
        type_name=unique("MultiRequestType"),
        element_name=request_name,
        state=request_state,
    )
    plugin_desc = PluginDesc(
        name=unique("multi_plugin"),
        description="python plugin",
        version="0.1",
        license="LGPL",
        source="ginext-gst",
        package="ginext-gst",
        origin="https://example.invalid",
        elements=(transform_cls, request_cls),
    )
    module = _make_plugin_module(plugin_desc)

    assert register_plugin_module(module) is True
    assert Gst.ElementFactory.find(transform_name) is not None
    assert Gst.ElementFactory.find(request_name) is not None


def test_plugin_module_rejects_duplicate_or_invalid_element_names() -> None:
    state = {
        "transform_ip": 0,
        "change_state": 0,
        "send_event": 0,
        "query": 0,
    }
    element_name = unique("invalid_transform").lower()
    cls = author_transform_class(
        type_name=unique("InvalidTransformType"),
        element_name=element_name,
        state=state,
    )
    cls.gimeta.extensions["Gst"]["registrations"][-1]["name"] = ""
    plugin_desc = PluginDesc(
        name=unique("invalid_plugin"),
        description="python plugin",
        version="0.1",
        license="LGPL",
        source="ginext-gst",
        package="ginext-gst",
        origin="https://example.invalid",
        elements=(cls,),
    )
    module = _make_plugin_module(plugin_desc)

    assert register_plugin_module(module) is False


def test_plugin_module_preserves_authored_rank_and_plugin_metadata_in_registry() -> (
    None
):
    state = {
        "transform_ip": 0,
        "change_state": 0,
        "send_event": 0,
        "query": 0,
    }
    element_name = unique("rank_transform").lower()
    cls = author_transform_class(
        type_name=unique("RankTransformType"),
        element_name=element_name,
        state=state,
    )
    cls.gimeta.extensions["Gst"]["registrations"][-1]["rank"] = Gst.Rank.PRIMARY
    plugin_desc = PluginDesc(
        name=unique("rank_plugin"),
        description="ranked python plugin",
        version="0.1",
        license="LGPL",
        source="ginext-gst",
        package="ginext-gst",
        origin="https://example.invalid",
        elements=(cls,),
    )
    module = _make_plugin_module(plugin_desc)

    assert register_plugin_module(module) is True

    plugin = Gst.Registry.get().find_plugin(plugin_desc.name)
    factory = Gst.ElementFactory.find(element_name)
    assert plugin is not None
    assert plugin.get_description() == plugin_desc.description
    assert plugin.get_version() == plugin_desc.version
    assert factory is not None
    assert factory.get_rank() == Gst.Rank.PRIMARY
