# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango

from .support import make_context, run_subprocess_probe


def probe_fontset_metrics_and_font_lookup() -> bool:
    fontset = make_context().load_fontset(
        Pango.FontDescription.from_string("Sans 12"),
        Pango.Language.from_string("en"),
    )

    assert fontset is not None
    assert fontset.get_metrics().get_ascent() > 0
    assert fontset.get_font(65) is not None
    return True

def test_fontset_exposes_metrics_and_font_lookup() -> None:
    assert run_subprocess_probe(__file__, "probe_fontset_metrics_and_font_lookup") is True
