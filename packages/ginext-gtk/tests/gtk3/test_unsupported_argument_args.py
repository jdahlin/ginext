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

"""Gtk-3.0-family inventory backlog tests."""

from __future__ import annotations

import pytest

from ginext import private
from ginext.tests.inventory.test_unsupported_argument_args import (
    _load_snapshot,
    _snapshot_param,
    callable_info as callable_info,
    loaded_namespaces as loaded_namespaces,
)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "qualified" not in metafunc.fixturenames:
        return
    entries = [entry for entry in _load_snapshot() if entry.get("is_gtk3")]
    if not entries:
        metafunc.parametrize(
            "namespace,version,qualified,kind",
            [
                pytest.param(
                    "",
                    "",
                    "",
                    "",
                    marks=pytest.mark.skip(
                        reason="snapshot has no Gtk-3.0-family unsupported argument entries"
                    ),
                )
            ],
        )
        return
    metafunc.parametrize(
        "namespace,version,qualified,kind",
        [_snapshot_param(entry) for entry in entries],
    )


def test_argument_arg_descriptor_builds(
    qualified: str,
    callable_info: tuple[object, bool],
    kind: str,
) -> None:
    info, has_self = callable_info
    private.build_callable_descriptor(info, qualified, has_self)
