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

"""Gtk namespace overlay — thin dispatcher.

Each concern lives in its own module; importing it runs the overlay
registrations.  The bootstrap calls `apply_to_namespace` if present, but all
registration here happens at import time via the decorator-based overlay API.
"""

from __future__ import annotations

from ginext import Gtk
from ginext_gtk._gtktemplate import Template
from ginext_gtk._overlays import (
    css,
    expression,
    gtk3_actions,
    gtk3_builder,
    gtk3_dialogs,
    gtk3_legacy,
    text,
)

overlay = Gtk.overlay
overlay.constant("Template", Template)

__all__ = [
    "css",
    "expression",
    "gtk3_actions",
    "gtk3_builder",
    "gtk3_dialogs",
    "gtk3_legacy",
    "text",
]
