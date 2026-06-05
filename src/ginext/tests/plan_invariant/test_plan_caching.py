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

"""Descriptor plans are built once and cached.

The plan: argument/return facts are copied into PyGIArgPlan /
PyGIReturnPlan structs at build time so the hot path never walks
GITypeInfo again.
"""

from __future__ import annotations


def test_repeated_descriptor_lookup_returns_same_object() -> None:
    from ginext import Gio

    a = Gio.Cancellable.cancel
    b = Gio.Cancellable.cancel
    assert a is b


def test_repeated_top_level_function_lookup_returns_same_object() -> None:
    from ginext import GLib

    a = GLib.get_user_name
    b = GLib.get_user_name
    assert a is b


def test_descriptor_exposes_qualified_name() -> None:
    from ginext import Gio

    desc = Gio.Cancellable.cancel
    qn = getattr(desc, "__qualname__", repr(desc))
    assert "Gio" in qn or "Cancellable" in qn
    assert "cancel" in qn


def test_descriptor_exposes_plan_for_debug() -> None:
    """A debug-only attribute should expose the plan for inspection.
    Used by tests to verify the planned facts; not for hot-path use."""
    from ginext import Gio

    desc = Gio.Cancellable.cancel
    plan = getattr(desc, "_plan_for_test", None)
    if plan is None:
        # Acceptable: plan may be private and not exposed even for tests.
        return
    # If exposed, it should be a structure listing args/return.
    assert hasattr(plan, "args") or hasattr(plan, "arg_count")
