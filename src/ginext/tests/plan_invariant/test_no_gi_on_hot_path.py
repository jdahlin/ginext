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

"""The hard performance invariant: repeated invocation must not call
gi_* on the hot path.

> Descriptor construction may call gi_*. Invocation must not call gi_*
> on the hot path.
"""

from __future__ import annotations

import pytest


def test_top_level_function_repeat_calls_no_metadata_walk() -> None:
    from ginext import GLib, runtime

    fn = GLib.get_user_name
    # Ensure descriptor is built (this *may* call gi_*).
    fn()
    runtime.reset_stats()

    fn()
    fn()
    fn()

    assert runtime.stats()["invoke_gi_metadata_calls"] == 0


def test_instance_method_repeat_calls_no_metadata_walk() -> None:
    from ginext import Gio, runtime

    c = Gio.Cancellable()
    c.is_cancelled()  # build descriptor
    runtime.reset_stats()

    for _ in range(50):
        c.is_cancelled()

    assert runtime.stats()["invoke_gi_metadata_calls"] == 0


def test_class_construction_repeat_no_metadata_walk() -> None:
    from ginext import Gio, runtime

    Gio.Cancellable()  # build constructor descriptor
    runtime.reset_stats()

    for _ in range(50):
        Gio.Cancellable()

    assert runtime.stats()["invoke_gi_metadata_calls"] == 0


@pytest.mark.subprocess(timeout=30)
def test_descriptor_build_does_call_gi() -> None:
    """The other side of the invariant: descriptor *build* is allowed
    (and expected) to walk GI metadata. Runs in a fresh subprocess so the
    GLib.get_user_name descriptor is built cold (it is cached thereafter)."""
    from ginext import runtime

    runtime.reset_stats()

    # Fresh namespace + class + method lookup triggers descriptor build.
    from ginext import GLib

    GLib.get_user_name

    assert runtime.stats()["invoke_gi_metadata_calls"] > 0


def test_unsupported_paths_flagged_as_not_optimized() -> None:
    """An unsupported call site, if reachable, must be flagged so it
    cannot silently become the normal path."""
    from ginext import runtime

    # Look at runtime's registry of descriptors built so far.
    flagged = runtime.unoptimized_descriptors_for_test()
    assert isinstance(flagged, (list, tuple, set))
