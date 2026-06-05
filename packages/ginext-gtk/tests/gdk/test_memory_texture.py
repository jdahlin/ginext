# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gdk

from .support import make_texture


def test_memory_texture_exposes_dimensions_format_and_serialization() -> None:
    texture = make_texture()

    assert texture.get_width() == 1
    assert texture.get_height() == 1
    assert texture.get_intrinsic_width() == 1
    assert texture.get_intrinsic_height() == 1
    assert texture.get_format() == Gdk.MemoryFormat.R8G8B8A8_PREMULTIPLIED
    assert texture.get_flags() == 3
    assert texture.get_current_image() is texture
    assert texture.get_intrinsic_aspect_ratio() == 1.0
    assert texture.equal(texture) is True
    assert texture.hash() > 0
    assert texture.serialize()[0] == "bytes"
    assert texture.save_to_png_bytes().get_size() > 0
    assert texture.save_to_tiff_bytes().get_size() > 0
