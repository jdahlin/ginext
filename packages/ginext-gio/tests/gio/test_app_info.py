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

import sys

import pytest


def test_get_all_returns_object_wrappers() -> None:
    from ginext import Gio, GObject

    app_infos = Gio.app_info_get_all()

    assert isinstance(app_infos, list)
    if sys.platform == "win32":
        # The concrete GWin32AppInfo type is not in any loaded typelib, so the
        # entries wrap as the Gio.AppInfo interface rather than a concrete
        # GObject.Object subclass. They are still usable AppInfo wrappers.
        assert all(isinstance(info, Gio.AppInfo) for info in app_infos)
    else:
        assert all(isinstance(info, GObject.Object) for info in app_infos)


@pytest.mark.skipif(
    sys.platform in ("darwin", "win32"),
    reason="GAppInfo.create_from_commandline is unsupported by the macOS backend "
    "and the Windows backend normalizes the command line (drops %f)",
)
def test_create_from_commandline_returns_appinfo_wrapper() -> None:
    from ginext import Gio

    app = Gio.AppInfo.create_from_commandline(
        "sh -c true",
        "Ginext Test",
        Gio.AppInfoCreateFlags.NONE,
    )

    assert app is not None
    assert isinstance(app, Gio.AppInfo)
    assert app.get_name() == "Ginext Test"
    assert app.get_commandline() == "sh -c true %f"
    assert app.supports_files() is True
    assert app.supports_uris() is False
