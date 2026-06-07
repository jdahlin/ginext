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

"""Python-owned class construction from GI info objects.

Classes are built with type(...) and installed on the namespace lazily.
"""

from __future__ import annotations

import pytest


def test_class_is_a_type() -> None:
    from ginext import Gio

    assert isinstance(Gio.Cancellable, type)


def test_class_module_is_namespace_qualified() -> None:
    """Generated classes should report a module-like __module__ so that
    pickling/repr behaves predictably."""
    from ginext import Gio

    assert Gio.Cancellable.__module__ in ("ginext.Gio", "Gio", "ginext")


def test_class_qualname_matches_simple_name() -> None:
    from ginext import Gio

    assert Gio.Cancellable.__qualname__ == "Cancellable"


def test_class_name_matches_gi_name() -> None:
    from ginext import Gio

    assert Gio.Cancellable.__name__ == "Cancellable"


def test_imported_class_gi_info_lives_on_gimeta() -> None:
    from ginext import Gio

    assert "__gi_info__" not in Gio.Cancellable.__dict__
    assert Gio.Cancellable.gimeta.gi_info is not None


def test_class_repr_includes_namespace() -> None:
    from ginext import Gio

    r = repr(Gio.Cancellable)
    assert "Cancellable" in r


@pytest.mark.subprocess(timeout=30)
def test_class_construction_is_lazy() -> None:
    """Accessing one class should not eagerly build every class in the
    namespace. Runs in a fresh subprocess so the Gio namespace starts cold
    (classes are built lazily and cached for the life of the process)."""
    import ginext

    gio = ginext.Gio

    built_before = set(gio.__dict__)
    _ = gio.Cancellable
    built_after = set(gio.__dict__)

    assert "Cancellable" in built_after - built_before
    assert "Application" not in built_after


def test_method_descriptor_does_not_rebuild_plan() -> None:
    from ginext import runtime
    import ginext

    cancellable_type = ginext.Gio.Cancellable

    cancellable = cancellable_type()
    runtime.reset_stats()
    assert cancellable.is_cancelled() is False

    runtime.reset_stats()
    assert cancellable.is_cancelled() is False

    assert runtime.stats()["plan_gi_metadata_calls"] == 0


def test_native_wrap_does_not_fall_back_to_compat_profile_for_gio_objects() -> None:
    gi_repository = pytest.importorskip("gi.repository")
    # DesktopAppInfo is a Linux-only GioUnix API: the GioUnix namespace itself is
    # absent on Windows (accessing it raises AttributeError) and present-but-
    # without-DesktopAppInfo on macOS.
    gio_unix = getattr(gi_repository, "GioUnix", None)
    if gio_unix is None or not hasattr(gio_unix, "DesktopAppInfo"):
        pytest.skip("GioUnix.DesktopAppInfo not available on this platform")

    from ginext import Gio, GObject

    app_infos = Gio.app_info_get_all()
    if not app_infos:
        pytest.skip("no desktop app infos available")

    first = app_infos[0]
    assert isinstance(first, GObject.Object)
    assert not type(first).__module__.startswith("gi.repository.")
