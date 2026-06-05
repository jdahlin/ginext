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

"""Implied co-required versions for the Gtk ecosystem.

Exposed to ginext core via the ``ginext.implied_defaults`` entry point: when a
project pins a Gtk version, these name the matching versions of the namespaces
that travel with it (Gdk, Gsk, GtkSource, WebKit). Kept here rather than in core
so core carries no Gtk-specific configuration.
"""

from __future__ import annotations

IMPLIED_DEFAULTS: dict[tuple[str, str], dict[str, str]] = {
    ("Gtk", "4.0"): {
        "Gdk": "4.0",
        "Gsk": "4.0",
        "GtkSource": "5",
        "WebKit": "6.0",
    },
    ("Gtk", "3.0"): {
        "Gdk": "3.0",
        "GtkSource": "4",
        "WebKit2": "4.1",
    },
}
