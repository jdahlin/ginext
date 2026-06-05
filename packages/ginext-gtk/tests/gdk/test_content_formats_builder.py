# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gdk


def test_content_formats_builder_accumulates_formats() -> None:
    builder = Gdk.ContentFormatsBuilder.new()
    builder.add_mime_type("text/uri-list")
    builder.add_gtype(str)
    builder.add_formats(Gdk.ContentFormats.new(["text/plain", "text/html"]))

    formats = builder.to_formats()

    assert formats.get_mime_types() == ["text/uri-list", "text/plain", "text/html"]
    assert formats.get_gtypes()
