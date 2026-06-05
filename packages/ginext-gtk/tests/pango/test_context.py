# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango

from .support import make_context


def test_context_exposes_language_gravity_and_metrics() -> None:
    context = make_context()
    language = Pango.Language.from_string("en")
    desc = Pango.FontDescription.from_string("Sans 12")

    context.set_base_dir(Pango.Direction.LTR)
    context.set_base_gravity(Pango.Gravity.SOUTH)
    context.set_gravity_hint(Pango.GravityHint.STRONG)
    context.set_language(language)
    context.set_font_description(desc)

    assert context.get_base_dir() == Pango.Direction.LTR
    assert context.get_base_gravity() == Pango.Gravity.SOUTH
    assert context.get_gravity_hint() == Pango.GravityHint.STRONG
    assert context.get_language().to_string() == "en"
    assert context.get_font_description().to_string() == "Sans 12"
    assert context.get_font_map() is not None
    assert context.get_serial() >= 0

    metrics = context.get_metrics(desc, language)
    assert metrics.get_ascent() > 0
    assert metrics.get_descent() >= 0
    assert metrics.get_approximate_char_width() > 0


def test_context_lists_families_and_loads_font_objects() -> None:
    context = make_context()
    desc = Pango.FontDescription.from_string("Sans 12")
    language = Pango.Language.from_string("en")

    families = context.list_families()
    assert families

    font = context.load_font(desc)
    assert font is not None
    assert font.describe().get_family() is not None

    fontset = context.load_fontset(desc, language)
    assert fontset is not None
    assert fontset.get_metrics().get_ascent() > 0
    assert fontset.get_font(65) is not None
