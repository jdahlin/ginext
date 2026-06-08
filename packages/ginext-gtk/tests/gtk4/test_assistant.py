# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import pytest


@pytest.mark.filterwarnings("ignore:Deprecated since 4.10.:DeprecationWarning")
def test_assistant_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display
    from ginext import Gtk

    assistant = Gtk.Assistant()
    first = Gtk.Label(label="first")
    second = Gtk.Label(label="second")

    assistant.append_page(first)
    assistant.append_page(second)

    assert len(assistant) == 2
    assert list(assistant) == [first, second]
    assert assistant[0] is first
    assert assistant[-1] is second
    assert assistant[:] == [first, second]
