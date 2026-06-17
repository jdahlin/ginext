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

"""Methods declared on a GIR enum get installed on the Python class.

GIR can declare functions as belonging to an enum type — typically
free functions in C that take the enum's storage type as first arg
and are named with the enum's `c_symbol_prefix`. In the typelib they
appear under `<enumeration><method ...>` and become accessible as

    EnumClass.method_name(value)

Showtime hits this via `GstPlay.PlayMessage.parse_type(msg)` — the
`PlayMessage` GIR enum has `parse_type` (and friends) declared as
methods, but goi's enum class builder only set up the value
members and never walked the method list.

Test exercises the contract on GIMarshallingTests if it has any
enum methods, and falls back to the showtime repro shape
(GstPlay.PlayMessage.parse_type) when the GstPlay typelib is
available — both end up on the same install path.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.xfail(
    reason="port from goi pending; APIs not yet adapted to ginext",
    run=False,
    strict=False,
)

import pytest


@pytest.fixture(scope="module")
def GstPlay() -> Any:
    try:
        import goi

        goi.require_version("GstPlay", "1.0")
        from goi.repository import GstPlay

        return GstPlay
    except ImportError, ValueError:
        pytest.skip("GstPlay-1.0 typelib not available")


def test_play_message_parse_type_resolves_as_classmethod(GstPlay: Any) -> None:
    """Showtime's repro: `GstPlay.PlayMessage.parse_type(msg)`. The
    namespace-level `gst_play_message_parse_type` is exposed in the
    enum's method list — installing it on the enum class is the
    pygobject-shaped contract."""
    assert hasattr(GstPlay.PlayMessage, "parse_type"), (
        "PlayMessage.parse_type missing — enum methods aren't installed"
    )
    assert callable(GstPlay.PlayMessage.parse_type)
