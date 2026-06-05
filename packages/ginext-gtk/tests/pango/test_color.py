# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_color_parse_copy_and_stringify() -> None:
    color = Pango.Color()

    assert color.parse("#112233") is True
    assert color.to_string() == "#111122223333"

    parsed, alpha = color.parse_with_alpha("#11223344")
    assert parsed is True
    assert alpha == 17476

    copy = color.copy()
    assert copy is not None
    assert copy.to_string() == color.to_string()
