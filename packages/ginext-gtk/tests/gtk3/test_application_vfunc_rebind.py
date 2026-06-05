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

"""Vfunc descriptor rebind across a cross-namespace inheritance chain.

Relocated from the core GObject vfunc tests: the mechanism is core, but this
case can only be exercised through Gtk.Application (a Gtk-namespace subclass of
Gio.Application), so it belongs in the Gtk suite.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xdist_group("gtk3")


def test_chain_up_rebinds_implementor_to_accessing_class() -> None:
    """Vfunc inheritance via Python MRO: `startup` is introspected on
    Gio.Application but accessed via Gtk.Application.do_startup. The
    descriptor protocol must rebind the implementor to the accessing
    class (Gtk.Application's GType), not the install-time class
    (Gio.Application's GType), so the chain-up dispatches through the
    accessing class's own class struct slot — which is what triggers
    Gtk/Adw-specific startup logic. Without the rebind, chaining up
    to `Adw.Application.do_startup` from a subclass override
    segfaults at runtime.

    Pinned to the gtk3 group so the process uses one Gtk version."""
    from ginext import Gtk, Gio

    # startup is defined on Gio.Application; Gtk.Application inherits it.
    # The descriptor must rebind to Gtk.Application when accessed there.
    on_gio = repr(Gio.Application.do_startup)
    on_gtk = repr(Gtk.Application.do_startup)
    assert "GApplication" in on_gio
    assert "GtkApplication" in on_gtk
