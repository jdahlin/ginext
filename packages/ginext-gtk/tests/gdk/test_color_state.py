# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_texture


def test_color_state_equality_and_singletons_are_available() -> None:
    from ginext import Gdk

    state = make_texture().get_color_state()

    assert state.equal(state) is True
    assert Gdk.ColorState.get_srgb() is not None
    assert Gdk.ColorState.get_srgb_linear() is not None
    assert Gdk.ColorState.get_rec2100_pq() is not None
