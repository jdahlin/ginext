# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_font_map


def test_font_map_creates_context_and_lists_families() -> None:
    font_map = make_font_map()
    context = font_map.create_context()
    families = font_map.list_families()

    assert context.get_font_map() is font_map
    assert families
    assert font_map.get_serial() >= 0
    assert font_map.get_family(families[0].get_name()) is not None
