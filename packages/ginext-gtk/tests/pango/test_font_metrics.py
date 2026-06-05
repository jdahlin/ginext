# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango

from .support import make_context


def test_font_metrics_exposes_scalar_measurements() -> None:
    metrics = make_context().get_metrics(
        Pango.FontDescription.from_string("Sans 12"),
        Pango.Language.from_string("en"),
    )

    assert metrics.get_ascent() > 0
    assert metrics.get_descent() >= 0
    assert metrics.get_height() > 0
    assert metrics.get_approximate_char_width() > 0
    assert metrics.get_approximate_digit_width() > 0
    assert metrics.get_strikethrough_position() >= 0
    assert metrics.get_strikethrough_thickness() > 0
    assert metrics.get_underline_position() <= 0
    assert metrics.get_underline_thickness() > 0
