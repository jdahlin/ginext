# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any

import pytest

from ginext import Pango, PangoCairo

# Re-export explicitly so `from .support import run_subprocess_probe`
# type-checks under --strict.
try:
    from subprocess_support import run_subprocess_probe as run_subprocess_probe
except ModuleNotFoundError:
    from tests.subprocess_support import (  # type: ignore[import-not-found, no-redef]
        run_subprocess_probe as run_subprocess_probe,
    )


def make_font_map() -> Any:
    return PangoCairo.FontMap.new()


def make_context() -> Any:
    return make_font_map().create_context()


def make_layout(text: str = "Hello world") -> Any:
    layout = Pango.Layout.new(make_context())
    layout.set_text(text, -1)
    return layout


def make_family_with_faces() -> Any:
    for family in make_context().list_families():
        if family.list_faces():
            return family
    pytest.skip("Pango font families with faces are not available in this environment")
