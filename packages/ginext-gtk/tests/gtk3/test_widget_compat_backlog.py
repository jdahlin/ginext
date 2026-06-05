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

"""Gtk smoke tests against the system Gtk typelibs."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def Gtk() -> Any:
    from ginext import Gtk

    if Gtk.get_major_version() != 3:
        pytest.skip("requires Gtk-3.0")
    return Gtk


@pytest.fixture
def Gio() -> Any:
    from ginext import Gio

    return Gio


def _new_window(Gtk: Any) -> Any:
    return Gtk.Window.new(Gtk.WindowType.TOPLEVEL)


def test_enums(Gtk: Any) -> None:
    assert int(Gtk.Orientation.HORIZONTAL) == 0
    assert int(Gtk.Orientation.VERTICAL) == 1
    assert int(Gtk.Align.FILL) == 0
    assert int(Gtk.Align.CENTER) == 3


def test_application_flags(Gtk: Any) -> None:
    assert hasattr(Gtk.Application, "new")


def test_widget_visible_round_trip(Gtk: Any) -> None:
    w = Gtk.Label.new("x")
    w.set_visible(False)
    assert w.get_visible() is False
    w.set_visible(True)
    assert w.get_visible() is True


def test_widget_name_round_trip(Gtk: Any) -> None:
    w = Gtk.Label.new("x")
    assert w.get_name() == "GtkLabel"
    w.set_name("hello")
    assert w.get_name() == "hello"


def test_widget_set_size_request(Gtk: Any) -> None:
    Gtk.Label.new("x").set_size_request(640, 480)


def test_window_is_widget(Gtk: Any) -> None:
    win = _new_window(Gtk)
    assert isinstance(win, Gtk.Widget)


def test_window_title(Gtk: Any) -> None:
    win = _new_window(Gtk)
    win.set_title("Test")
    assert win.get_title() == "Test"


def test_window_child(Gtk: Any) -> None:
    win = _new_window(Gtk)
    assert win.get_child() is None
    label = Gtk.Label.new("hi")
    win.add(label)
    assert isinstance(win.get_child(), Gtk.Widget)


def test_box_enum_arg(Gtk: Any) -> None:
    box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
    assert isinstance(box, Gtk.Widget)
    assert box.get_spacing() == 12
    assert box.get_orientation() == Gtk.Orientation.VERTICAL


def test_box_set_spacing(Gtk: Any) -> None:
    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    box.set_spacing(8)
    assert box.get_spacing() == 8


def test_box_append(Gtk: Any) -> None:
    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    label = Gtk.Label.new("x")
    box.pack_start(label, False, False, 0)


def test_label_nullable_ctor(Gtk: Any) -> None:
    assert Gtk.Label.new("hi").get_label() == "hi"
    assert Gtk.Label.new(None).get_label() == ""


def test_label_set(Gtk: Any) -> None:
    label = Gtk.Label.new("a")
    label.set_label("b")
    assert label.get_label() == "b"


def test_application(Gtk: Any, Gio: Any) -> None:
    app = Gtk.Application.new("org.example.App", Gio.ApplicationFlags.NON_UNIQUE)
    assert app.get_application_id() == "org.example.App"


def test_application_nullable_id(Gtk: Any, Gio: Any) -> None:
    app = Gtk.Application.new(None, Gio.ApplicationFlags.NON_UNIQUE)
    assert app.get_application_id() is None


pytestmark = pytest.mark.xdist_group("gtk3")
