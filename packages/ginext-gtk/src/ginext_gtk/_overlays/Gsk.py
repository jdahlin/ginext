# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from ginext import Gsk

if TYPE_CHECKING:
    from collections.abc import Callable


overlay = Gsk.overlay


# Stroke.get_dash: GIR models as (list|None, count) tuple; ginext returns list.
@overlay.method("Stroke", name="get_dash")
def _stroke_get_dash(
    fn: Callable[[Gsk.Stroke], list[float]], self: Gsk.Stroke
) -> list[float]:
    return list(fn(self))


@overlay.method("Path", name="__str__")
def _path_str(self: Gsk.Path) -> str:
    return str(self.to_string())


@overlay.method("Path", name="__repr__")
def _path_repr(self: Gsk.Path) -> str:
    return f"Gsk.Path({self.to_string()!r})"


@overlay.method("Transform", name="__repr__")
def _transform_repr(self: Gsk.Transform) -> str:
    return f"Gsk.Transform({self.to_string()!r})"
