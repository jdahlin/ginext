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

"""Gtk.Adjustment constructor behavior."""

from __future__ import annotations

import pytest


def test_initially_unowned_subclass_is_not_floating_after_construct() -> None:
    pytest.importorskip("ginext")
    from ginext import Gtk

    adj = Gtk.Adjustment()
    # Reaching into the C-level "is_floating" via a test hook on the
    # wrapper. If no such hook exists, this test documents the
    # expectation (and forces the implementer to expose one).
    assert adj.is_floating() is False


def test_constructor_with_kwargs_also_sinks_floating_ref() -> None:
    pytest.importorskip("ginext")
    from ginext import Gtk

    adj = Gtk.Adjustment(upper=10.0)
    assert adj.get_upper() == 10.0
    assert adj.is_floating() is False


def test_subclass_can_pass_kwargs_to_base() -> None:
    pytest.importorskip("ginext")
    from ginext import Gtk

    class MyAdjustment(Gtk.Adjustment):
        pass

    adj = MyAdjustment(upper=12.5)
    assert adj.get_upper() == 12.5


def test_wrong_scalar_value_rejected_as_construct_property() -> None:
    pytest.importorskip("ginext")
    from ginext import Gtk

    with pytest.raises(TypeError, match="real number"):
        Gtk.Adjustment(upper=object())  # type: ignore[arg-type]  # deliberately passes wrong type to test error handling


def test_invalid_bounds_raise_instead_of_returning_none() -> None:
    pytest.importorskip("ginext")
    from ginext import Gtk

    with pytest.raises(RuntimeError, match="returned NULL"):
        Gtk.Adjustment.new(0, 0, 1, 1, 4096, 4096)
