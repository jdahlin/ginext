# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from typing import Any

import pytest

try:
    from ginext import Adw
except ImportError:
    pytest.skip("Adw (libadwaita) namespace not available", allow_module_level=True)


def test_close_page_method_signal_collision(require_gtk4_display: Any) -> None:
    Gtk = require_gtk4_display

    view = Adw.TabView()
    page = view.append(Gtk.Label(label="Terminal"))
    seen: list[Any] = []

    def on_close_page(tab_view: Any, tab_page: Any) -> bool:
        seen.append(tab_page)
        tab_view.close_page_finish(tab_page, True)
        return True

    view.close_page.connect(on_close_page)
    view.close_page(page)

    assert seen == [page]
    assert view.get_n_pages() == 0
