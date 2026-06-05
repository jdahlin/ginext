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

"""Port of goi/tests/test_lazy_namespace.py for ginext's namespace path."""

from __future__ import annotations

import getpass
import time

import pytest


def test_open_glib() -> None:
    import ginext

    assert "GLib" in repr(ginext.GLib)


def test_glib_get_user_name_resolves_and_calls() -> None:
    from ginext import GLib

    fn = GLib.get_user_name

    assert callable(fn)
    assert "get_user_name" in repr(fn)
    assert fn.__name__ == "get_user_name"
    assert fn() == getpass.getuser()


def test_repeated_resolve_until_cache_lands() -> None:
    from ginext import GLib

    expected = getpass.getuser()
    for _ in range(50):
        assert GLib.get_user_name() == expected


def test_unknown_attribute_raises() -> None:
    from ginext import GLib

    with pytest.raises(AttributeError, match="get_user_name_xxxxx"):
        _ = GLib.get_user_name_xxxxx


def test_shell_parse_argv_works() -> None:
    from ginext import GLib

    ok, argv = GLib.shell_parse_argv("ls -la")

    assert ok is True
    assert argv == ["ls", "-la"]


def test_overlay_exports_shadowed_name() -> None:
    from ginext import GLib

    fn = GLib.timeout_add

    assert callable(fn)
    assert fn.__name__ == "timeout_add"


def test_null_terminated_string_array_return() -> None:
    from ginext import GLib

    env = GLib.get_environ()

    assert isinstance(env, list)
    assert env
    assert all(isinstance(value, str) for value in env)


def test_int64_return_shape() -> None:
    from ginext import GLib

    t1 = GLib.get_monotonic_time()
    t2 = GLib.get_monotonic_time()

    assert isinstance(t1, int)
    assert isinstance(t2, int)
    assert t1 > 0
    assert t2 >= t1


def test_int64_real_time() -> None:
    from ginext import GLib

    gtime = GLib.get_real_time()
    pytime_us = int(time.time() * 1_000_000)

    assert abs(gtime - pytime_us) < 1_000_000


def test_object_class_resolves_and_constructs() -> None:
    from ginext import Gio

    cancellable = Gio.Cancellable

    assert cancellable.__name__ == "Cancellable"
    assert cancellable.__module__ in {"ginext.Gio", "Gio", "ginext"}
    assert hasattr(cancellable, "gimeta")

    inst = cancellable()

    assert isinstance(inst, cancellable)
    assert hasattr(type(inst), "gimeta")
    assert "Gio.Cancellable" in repr(inst)


def test_distinct_classes_lookup() -> None:
    from ginext import Gio

    assert Gio.Cancellable is not Gio.SimpleAction  # type: ignore[comparison-overlap]
    assert Gio.Cancellable.__name__ == "Cancellable"
    assert Gio.SimpleAction.__name__ == "SimpleAction"
