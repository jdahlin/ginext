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

"""Shared collection hooks for the typelib tests.

GIMarshallingTests guards a handful of POSIX integer-type helpers
(dev_t/gid_t/pid_t/socklen_t/uid_t) behind ``G_OS_UNIX``, so they are
absent from the typelib on non-Unix platforms (e.g. Windows). Rather
than hard-coding a ``sys.platform`` skip, probe the built namespace and
skip the corresponding tests only when the symbol genuinely is not
present, keeping the suite green wherever the helper does exist.
"""

from __future__ import annotations

import pytest

# Test-name prefixes whose underlying GIMarshallingTests symbol may be
# compiled out on non-Unix builds. The symbol name is the test name with the
# leading "test_" removed (e.g. test_pid_t_in -> pid_t_in).
_OPTIONAL_POSIX_PREFIXES = (
    "test_dev_t_",
    "test_gid_t_",
    "test_pid_t_",
    "test_socklen_t_",
    "test_uid_t_",
)


def _gimarshalling_symbols() -> set[str] | None:
    try:
        import ginext

        ns = ginext._load_namespace("GIMarshallingTests", "1.0")
    except Exception:
        return None
    return {name for name in dir(ns) if not name.startswith("_")}


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    symbols: set[str] | None = None
    probed = False
    for item in items:
        name = item.originalname if isinstance(item, pytest.Function) else item.name
        if not name.startswith(_OPTIONAL_POSIX_PREFIXES):
            continue
        if not probed:
            symbols = _gimarshalling_symbols()
            probed = True
        if symbols is None:
            continue
        symbol = name[len("test_") :]
        if symbol not in symbols:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"GIMarshallingTests.{symbol} is not built on this "
                        "platform (POSIX-only type)"
                    )
                )
            )
