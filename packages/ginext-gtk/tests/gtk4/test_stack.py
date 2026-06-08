# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations


def test_stack_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display
    from ginext import Gtk

    stack = Gtk.Stack()
    first = stack.add_named(Gtk.Label(label="first"), "first")
    second = stack.add_named(Gtk.Label(label="second"), "second")

    assert len(stack) == 2
    assert list(stack) == [first, second]
    assert stack[0] is first
    assert stack[-1] is second
    assert stack[:] == [first, second]
