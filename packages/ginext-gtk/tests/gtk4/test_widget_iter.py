# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations


def test_widget_iter_yields_direct_children(require_gtk4_display: object) -> None:
    _ = require_gtk4_display
    from ginext import Gtk

    widget: Gtk.Widget = Gtk.Box()
    first = Gtk.Label(label="first")
    second = Gtk.Label(label="second")

    assert list(widget) == []

    box = widget
    assert isinstance(box, Gtk.Box)
    box.append(first)
    box.append(second)

    assert list(widget) == [first, second]
