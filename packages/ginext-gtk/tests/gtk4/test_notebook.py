# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations


def test_notebook_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display
    from ginext import Gtk

    notebook = Gtk.Notebook()
    first = Gtk.Label(label="first")
    second = Gtk.Label(label="second")

    notebook.append_page(first, Gtk.Label(label="First"))
    notebook.append_page(second, Gtk.Label(label="Second"))

    assert len(notebook) == 2
    assert list(notebook) == [first, second]
    assert notebook[0] is first
    assert notebook[-1] is second
    assert notebook[:] == [first, second]
