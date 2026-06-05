# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_layout


def test_path_builder_adds_segments_and_layouts() -> None:
    from ginext import Gsk

    builder = Gsk.PathBuilder.new()
    builder.move_to(0, 0)
    builder.line_to(10, 0)
    builder.rel_line_to(0, 10)
    builder.close()
    path = builder.to_path()

    assert path.is_empty() is False

    layout_builder = Gsk.PathBuilder.new()
    layout_builder.add_layout(make_layout())
    assert layout_builder.to_path().is_empty() is False
