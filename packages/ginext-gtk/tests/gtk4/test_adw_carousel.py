# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import pytest

try:
    from ginext import Adw, Gtk
except ImportError:
    pytest.skip("Adw (libadwaita) namespace not available", allow_module_level=True)


def test_carousel_collection_dunders(require_gtk4_display: object) -> None:
    _ = require_gtk4_display

    carousel = Adw.Carousel()
    first = Gtk.Label(label="One")
    second = Gtk.Label(label="Two")

    carousel.append(first)
    carousel.append(second)

    assert len(carousel) == 2
    assert list(carousel) == [first, second]
    assert carousel[0] is first
    assert carousel[-1] is second
    assert carousel[:] == [first, second]
