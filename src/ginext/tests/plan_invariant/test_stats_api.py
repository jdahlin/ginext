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

"""Runtime stats API.

The plan: "Add runtime stats for GI metadata calls used by invoke
planning and call paths. Tests should reset stats after descriptor
construction and assert repeated calls do not perform metadata walks."
"""

from __future__ import annotations


def test_stats_module_exists() -> None:
    from ginext import runtime

    assert hasattr(runtime, "stats")


def test_stats_returns_mapping() -> None:
    from ginext import runtime

    stats = runtime.stats()
    assert isinstance(stats, dict)


def test_stats_has_invoke_gi_metadata_calls_key() -> None:
    from ginext import runtime

    assert "invoke_gi_metadata_calls" in runtime.stats()


def test_reset_stats_zeroes_counter() -> None:
    from ginext import runtime

    # Trigger something that bumps the counter (descriptor build).
    from ginext import GLib

    GLib.get_user_name
    runtime.reset_stats()
    assert runtime.stats()["invoke_gi_metadata_calls"] == 0


def test_stats_is_a_snapshot_not_a_live_view() -> None:
    """Calling stats() should snapshot, so a later operation does not
    retroactively change a captured value."""
    from ginext import runtime

    runtime.reset_stats()
    snapshot = runtime.stats()
    # Trigger something that would bump counters.
    from ginext import GLib

    GLib.get_user_name()
    # The snapshot must not have changed.
    assert snapshot["invoke_gi_metadata_calls"] == 0
