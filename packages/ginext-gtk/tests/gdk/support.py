# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any

from ginext import Gdk

# Re-export explicitly so `from .support import run_subprocess_probe`
# type-checks under --strict.
try:
    from subprocess_support import run_subprocess_probe as run_subprocess_probe
except ModuleNotFoundError:
    from tests.subprocess_support import (  # type: ignore[import-not-found, no-redef]
        run_subprocess_probe as run_subprocess_probe,
    )


def make_rectangle(x: int, y: int, width: int, height: int) -> Any:
    rect = Gdk.Rectangle()
    rect.x = x
    rect.y = y
    rect.width = width
    rect.height = height
    return rect


def make_texture() -> Any:
    return Gdk.MemoryTexture.new(
        1,
        1,
        Gdk.MemoryFormat.R8G8B8A8_PREMULTIPLIED,
        b"\x10\x20\x30\xff",
        4,
    )
