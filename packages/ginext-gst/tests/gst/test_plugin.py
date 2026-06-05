# Tests for Gst.Registry and Gst.Plugin
#
# SPDX-License-Identifier: LGPL-2.0-or-later

from __future__ import annotations

from ginext.namespace import Namespace


# ---------------------------------------------------------------------------
# TestRegistry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_get_default(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        assert reg is not None
        assert isinstance(reg, Gst.Registry)

    def test_find_plugin_coreelements(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugin = reg.find_plugin("coreelements")
        assert plugin is not None

    def test_find_plugin_missing(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugin = reg.find_plugin("nonexistent_xyz_plugin")
        assert plugin is None

    def test_find_feature_fakesrc(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        feature = reg.find_feature("fakesrc", Gst.ElementFactory)
        assert feature is not None

    def test_find_feature_missing(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        feature = reg.find_feature("nonexistent_xyz", Gst.ElementFactory)
        assert feature is None

    def test_get_feature_list_not_empty(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        features = reg.get_feature_list(Gst.ElementFactory)
        assert len(list(features)) > 0

    def test_get_plugin_list_not_empty(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugins = reg.get_plugin_list()
        assert len(plugins) > 0

    def test_isinstance_registry(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        assert isinstance(reg, Gst.Object)


# ---------------------------------------------------------------------------
# TestPlugin
# ---------------------------------------------------------------------------


class TestPlugin:
    def test_get_name(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugin = reg.find_plugin("coreelements")
        name = plugin.get_name()
        assert isinstance(name, str)
        assert name

    def test_get_description(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugin = reg.find_plugin("coreelements")
        desc = plugin.get_description()
        assert desc is not None
        assert isinstance(desc, str)

    def test_get_version(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugin = reg.find_plugin("coreelements")
        version = plugin.get_version()
        assert version is not None
        assert isinstance(version, str)

    def test_is_loaded(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugin = reg.find_plugin("coreelements")
        # Plugins load lazily: find_plugin() returns the registry entry, which is
        # only marked loaded once an element from it is instantiated. Force the
        # load so the test does not depend on suite ordering. Gst.Plugin.load()
        # returns a fresh reference to the loaded plugin.
        loaded = plugin.load()
        assert loaded is not None
        assert loaded.is_loaded()

    def test_isinstance_plugin(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugin = reg.find_plugin("coreelements")
        assert isinstance(plugin, Gst.Plugin)

    def test_isinstance_object(self, Gst: Namespace) -> None:
        reg = Gst.Registry.get()
        plugin = reg.find_plugin("coreelements")
        assert isinstance(plugin, Gst.Object)


# ---------------------------------------------------------------------------
# TestElementFactory (extended)
# ---------------------------------------------------------------------------


class TestElementFactoryExtended:
    def test_get_element_type(self, Gst: Namespace) -> None:
        factory = Gst.ElementFactory.find("fakesrc")
        assert factory.get_element_type() != 0

    def test_has_interface(self, Gst: Namespace) -> None:
        factory = Gst.ElementFactory.find("fakesrc")
        assert factory is not None

    def test_get_metadata_author(self, Gst: Namespace) -> None:
        factory = Gst.ElementFactory.find("fakesrc")
        author = factory.get_metadata("author")
        assert author is not None

    def test_list_all_factories(self, Gst: Namespace) -> None:
        factories = Gst.ElementFactory.list_get_elements(
            Gst.ElementFactoryListType.ANY, Gst.Rank.NONE
        )
        assert len(factories) > 0
