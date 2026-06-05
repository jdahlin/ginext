# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_item_new_copy_and_char_offset_surface() -> None:
    item = Pango.Item.new()

    assert item.get_char_offset() == 0
    assert item.copy() is not None
