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

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any


def test_construct_property_and_methods(require_gtk4_display: Any) -> None:
    Gtk = require_gtk4_display

    button = Gtk.Button(label="Save")
    assert button.get_label() == "Save"

    button.set_label("Open")
    assert button.get_label() == "Open"


def test_clicked_action_signal(require_gtk4_display: Any) -> None:
    # "clicked" is an action signal (G_SIGNAL_ACTION), so the combined
    # `button.clicked` both connects and is callable-to-emit — no string
    # connect, no overlay shim.
    Gtk = require_gtk4_display

    button: Any = Gtk.Button()
    fired: list[object] = []
    conn = button.clicked.connect(lambda btn: fired.append(btn), owner=button)

    button.clicked()  # calling an action signal emits it
    button.clicked.emit()  # and explicit emit works too
    assert len(fired) == 2

    conn.disconnect()
    button.clicked()
    assert len(fired) == 2  # no longer connected
    # Identity check last: `is` narrows `button` to `object`, which would mask
    # the dynamic attribute access above under mypy --strict.
    assert fired[0] is button
