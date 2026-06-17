# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any, Generator

import pytest


_GI_MODULES = ("gi", "gi.repository", "gi.module", "gi._gi", "gi._signalhelper")


@pytest.fixture(autouse=True)
def _clean_features(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    import sys

    import ginext

    monkeypatch.delenv("GINEXT_FEATURES", raising=False)
    monkeypatch.delenv("GINEXT_GERROR_BUILTIN_EXCEPTIONS", raising=False)
    ginext.features.reset_for_test()
    for name in _GI_MODULES:
        sys.modules.pop(name, None)
    yield
    ginext.features.reset_for_test()
    for name in _GI_MODULES:
        sys.modules.pop(name, None)


def test_known_features_include_pygobject_compat_children() -> None:
    from ginext import features

    assert set(features.known_features()) >= {
        "pygobject_compat",
        "new_property_api",
        "new_signal_api",
        "gobject_property_constructor",
        "old_signal_api",
        "gerror_builtin_exceptions",
    }


def test_pygobject_compat_enables_children(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "pygobject_compat")

    from ginext import features

    assert features.is_enabled("pygobject_compat") is True
    assert features.is_enabled("new_property_api") is True
    assert features.is_enabled("new_signal_api") is True
    assert features.is_enabled("gobject_property_constructor") is True
    assert features.is_enabled("old_signal_api") is True


def test_explicit_child_disable_beats_pygobject_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "GINEXT_FEATURES",
        "pygobject_compat,-new_signal_api,gobject_property_constructor=0,old_signal_api=0",
    )

    from ginext import features

    assert features.is_enabled("pygobject_compat") is True
    assert features.is_enabled("new_property_api") is True
    assert features.is_enabled("new_signal_api") is False
    assert features.is_enabled("gobject_property_constructor") is False
    assert features.is_enabled("old_signal_api") is False


def test_programmatic_override_beats_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "pygobject_compat")

    from ginext import features

    features.set_enabled("new_property_api", False)

    assert features.is_enabled("new_property_api") is False


def test_unknown_feature_raises() -> None:
    from ginext import features

    with pytest.raises(KeyError):
        features.is_enabled("not_a_real_feature")


def test_new_signal_api_disable_blocks_attribute_signal_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "new_signal_api=0")

    from ginext import Gio

    obj = Gio.SimpleAction(name="feature-test")

    with pytest.raises(AttributeError):
        obj.notify


def test_new_property_api_can_be_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "new_property_api=0")

    from ginext.gobject.gobjectclass import Property

    with pytest.raises(TypeError, match="GObject.Property is disabled"):
        Property()


def test_gi_package_is_not_available_without_pygobject_compat() -> None:
    with pytest.raises(ModuleNotFoundError, match="No module named 'gi'"):
        __import__("gi")


def test_native_gobject_namespace_exposes_property_helper() -> None:
    import ginext
    from ginext import GObject

    assert GObject.Property is ginext.gobject.gobjectclass.Property


def test_pygobject_compat_enables_gi_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "pygobject_compat")

    import ginext
    import gi
    from gi.repository import GLib, GObject

    assert gi.repository.GLib is GLib
    assert GLib is not ginext.GLib
    assert GObject.GObject is ginext.gobject.gobjectclass.GObject
    # Compat exposes the getter/setter-capable Property subclass.
    assert GObject.Property is gi._propertyhelper.CompatProperty  # type: ignore[attr-defined]
    assert GObject.TYPE_INT is ginext.gobject.gtype.GType.INT
    assert GObject.Signal is gi._signalhelper.Signal
    assert GObject.SignalOverride is gi._signalhelper.SignalOverride


def test_gi_signalhelper_installs_signal_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "pygobject_compat")

    from gi import _signalhelper as signalhelper
    from gi.repository import GObject

    class Source:
        @GObject.Signal
        def changed(self, value: int) -> None:
            pass

    signalhelper.install_signals(Source)

    from typing import cast

    assert cast("Any", Source).__gsignals__ == {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, (int,), None, None)
    }
    assert cast("Any", Source).do_changed is not None


def test_gerror_builtin_exceptions_enabled_by_default() -> None:
    from ginext import features

    assert features.is_enabled("gerror_builtin_exceptions") is True


def test_pygobject_compat_disables_gerror_builtin_exceptions_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "pygobject_compat")

    from ginext import features

    assert features.is_enabled("gerror_builtin_exceptions") is False


def test_explicit_gerror_builtin_exceptions_beats_pygobject_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "GINEXT_FEATURES", "pygobject_compat,gerror_builtin_exceptions=1"
    )

    from ginext import features

    assert features.is_enabled("gerror_builtin_exceptions") is True


def test_gerror_builtin_direct_env_var_beats_pygobject_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_FEATURES", "pygobject_compat")
    monkeypatch.setenv("GINEXT_GERROR_BUILTIN_EXCEPTIONS", "true")

    from ginext import features

    assert features.is_enabled("gerror_builtin_exceptions") is True
