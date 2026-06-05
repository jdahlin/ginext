# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gsk


def test_parse_location_exposes_position_fields() -> None:
    location = Gsk.ParseLocation()
    location.bytes = 4
    location.chars = 5
    location.line_bytes = 6
    location.line_chars = 7
    location.lines = 8

    assert location.bytes == 4
    assert location.chars == 5
    assert location.line_bytes == 6
    assert location.line_chars == 7
    assert location.lines == 8
