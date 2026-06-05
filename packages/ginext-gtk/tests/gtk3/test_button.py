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

"""Gtk-3.0 button coverage ported from PyGObject override tests."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture(scope="module")
def Gtk() -> Any:
    from ginext import Gtk

    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    Gtk.init([])  # type: ignore[call-arg]  # Gtk3 init() accepts argv list; Gtk4 stubs have no-arg variant
    return Gtk


def test_button_constructs_as_container_widget(Gtk: Any) -> None:
    button = Gtk.Button()

    assert isinstance(button, Gtk.Button)
    assert isinstance(button, Gtk.Container)
    assert isinstance(button, Gtk.Widget)


def test_button_label_constructor(Gtk: Any) -> None:
    button = Gtk.Button(label="OK")

    assert button.get_label() == "OK"


def test_link_button_constructor(Gtk: Any) -> None:
    button = Gtk.LinkButton(uri="http://www.Gtk.org", label="Gtk")

    assert isinstance(button, Gtk.Button)
    assert isinstance(button, Gtk.Container)
    assert isinstance(button, Gtk.Widget)
    assert button.get_uri() == "http://www.Gtk.org"
    assert button.get_label() == "Gtk"


def test_button_stock_constructor(Gtk: Any) -> None:
    button = Gtk.Button.new_from_stock(Gtk.STOCK_CLOSE)

    assert button.get_label() == Gtk.STOCK_CLOSE
    assert button.get_use_stock() is True
    assert button.get_use_underline() is True


def test_clicked_action_signal(Gtk: Any) -> None:
    button: Any = Gtk.Button()
    clicked = button.clicked
    fired: list[object] = []
    conn = clicked.connect(lambda btn: fired.append(btn))

    clicked()
    clicked.emit()
    assert len(fired) == 2

    conn.disconnect()
    clicked()
    assert len(fired) == 2
    assert fired[0] is button
