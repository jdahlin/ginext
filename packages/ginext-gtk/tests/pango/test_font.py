# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango

from .support import make_context


def test_font_describes_metrics_coverage_and_map() -> None:
    context = make_context()
    font = context.load_font(Pango.FontDescription.from_string("Sans 12"))

    assert font is not None
    assert font.describe().get_family() is not None
    assert font.describe_with_absolute_size().get_family() is not None
    assert font.get_coverage(Pango.Language.from_string("en")) is not None
    assert font.get_metrics().get_ascent() > 0
    assert font.get_font_map() is not None

    extents = font.get_glyph_extents(65)
    assert extents.ink_rect is not None
    assert extents.logical_rect is not None
