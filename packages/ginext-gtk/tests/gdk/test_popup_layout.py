# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gdk

from .support import make_rectangle


def test_popup_layout_copies_and_updates_anchor_state() -> None:
    layout = Gdk.PopupLayout.new(
        make_rectangle(0, 0, 10, 10), Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH
    )

    assert layout.get_rect_anchor() == Gdk.Gravity.SOUTH
    assert layout.get_surface_anchor() == Gdk.Gravity.NORTH
    assert layout.get_offset() == (0, 0)

    layout.set_anchor_hints(Gdk.AnchorHints.FLIP_X | Gdk.AnchorHints.FLIP_Y)
    layout.set_offset(3, 4)
    layout.set_shadow_width(1, 2, 3, 4)
    copy = layout.copy()

    assert copy.equal(layout) is True
    assert copy.get_anchor_hints() == (
        Gdk.AnchorHints.FLIP_X | Gdk.AnchorHints.FLIP_Y
    )
    assert copy.get_offset() == (3, 4)
    assert copy.get_shadow_width() == (1, 2, 3, 4)
