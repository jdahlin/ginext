# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_tab_array_builds_resizes_and_round_trips() -> None:
    tabs = Pango.TabArray.new(2, True)
    tabs.set_tab(0, Pango.TabAlign.LEFT, 10)
    tabs.set_tab(1, Pango.TabAlign.DECIMAL, 30)

    assert tabs.get_size() == 2
    assert tabs.get_tab(0) == (Pango.TabAlign.LEFT, 10)
    assert tabs.get_tab(1) == (Pango.TabAlign.DECIMAL, 30)
    assert tabs.get_positions_in_pixels() is True
    assert tabs.to_string() == "10px\ndecimal:30px"

    parsed = Pango.TabArray.from_string(tabs.to_string())
    assert parsed is not None
    assert parsed.get_tab(1) == (Pango.TabAlign.DECIMAL, 30)
    assert len(tabs) == 2
    assert tabs[0] == (Pango.TabAlign.LEFT, 10)
    assert list(tabs) == [
        (Pango.TabAlign.LEFT, 10),
        (Pango.TabAlign.DECIMAL, 30),
    ]
    tab_repr = repr(tabs)
    assert tab_repr.startswith("Pango.TabArray([")
    assert "TabAlign.LEFT" in tab_repr
    assert "TabAlign.DECIMAL" in tab_repr
    assert "pixels=True" in tab_repr

    tabs.set_positions_in_pixels(False)
    assert tabs.get_positions_in_pixels() is False
    tabs.set_decimal_point(1, ord(","))  # type: ignore[arg-type]  # ord() returns int but Pango accepts Unicode codepoint int at runtime
    assert tabs.get_decimal_point(1) == ","
    tabs.resize(3)
    assert tabs.get_size() == 3
