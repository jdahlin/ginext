# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import pytest

try:
    from ginext import Adw
    from ginext import Gtk
except ImportError:
    pytest.skip("Adw (libadwaita) namespace not available", allow_module_level=True)


@pytest.mark.filterwarnings("ignore:Deprecated since 1.4.:DeprecationWarning")
def test_squeezer_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display

    squeezer = Adw.Squeezer()
    first = squeezer.add(Gtk.Label(label="first"))
    second = squeezer.add(Gtk.Label(label="second"))

    assert len(squeezer) == 2
    assert list(squeezer) == [first, second]
    assert squeezer[0] is first
    assert squeezer[-1] is second
    assert squeezer[:] == [first, second]


def test_view_stack_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display

    view_stack = Adw.ViewStack()
    first = view_stack.add_named(Gtk.Label(label="first"), "first")
    second = view_stack.add_named(Gtk.Label(label="second"), "second")

    assert len(view_stack) == 2
    assert list(view_stack) == [first, second]
    assert view_stack[0] is first
    assert view_stack[-1] is second
    assert view_stack[:] == [first, second]
