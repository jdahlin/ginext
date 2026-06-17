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

"""First vertical slice end-to-end.

From the plan:

    from ginext import GLib
    assert isinstance(GLib.get_user_name(), str)

    from ginext import Gio
    cancellable = Gio.Cancellable()
    cancellable.cancel()
    assert cancellable.is_cancelled()

This validates the whole pipeline: version resolution, namespace
import, top-level function descriptor, class construction, Pythonic
constructor adapter, instance method, GObject wrapping/unwrapping,
return marshalling, descriptor plan caching.
"""

from __future__ import annotations


def test_scalar_top_level_function() -> None:
    from ginext import GLib

    assert isinstance(GLib.get_user_name(), str)


def test_concrete_gobject_construct_and_method() -> None:
    from ginext import Gio

    cancellable = Gio.Cancellable()
    cancellable.cancel()
    assert cancellable.is_cancelled() is True


def test_full_pipeline_in_one_test() -> None:
    """Concatenate the two slices to verify they share state cleanly."""
    from ginext import GLib, Gio

    user = GLib.get_user_name()
    assert isinstance(user, str) and user

    c = Gio.Cancellable()
    assert c.is_cancelled() is False
    c.cancel()
    assert c.is_cancelled() is True
