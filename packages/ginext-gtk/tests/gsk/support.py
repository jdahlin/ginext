# SPDX-License-Identifier: LGPL-2.1-or-later

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from __future__ import annotations

from typing import Any

from ginext import Gdk, Graphene, Gsk, Pango, PangoCairo


def make_path() -> Any:
    builder = Gsk.PathBuilder.new()
    builder.move_to(0, 0)
    builder.line_to(10, 0)
    builder.line_to(10, 10)
    builder.close()
    return builder.to_path()


def make_transform() -> Any:
    point = Graphene.Point()
    point.init(2, 3)
    return Gsk.Transform.new().translate(point)


def make_layout() -> Any:
    font_map = PangoCairo.FontMap.new()
    context = font_map.create_context()
    layout = Pango.Layout.new(context)
    layout.set_text("Hi", -1)
    return layout


def make_rectangle() -> Any:
    rect = Gdk.Rectangle()
    rect.x = 0
    rect.y = 0
    rect.width = 20
    rect.height = 10
    return rect
