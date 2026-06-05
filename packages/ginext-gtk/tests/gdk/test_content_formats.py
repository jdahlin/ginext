# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Gdk

from .support import run_subprocess_probe


def test_content_formats_reports_mime_types_and_union() -> None:
    formats = Gdk.ContentFormats.new(["text/plain", "text/html"])

    assert formats.is_empty() is False
    assert len(formats) == 2
    assert list(formats) == ["text/plain", "text/html"]
    assert "text/plain" in formats
    assert formats.get_mime_types() == ["text/plain", "text/html"]
    assert formats.contain_mime_type("text/plain") is True
    assert formats.to_string() == "text/plain text/html"
    assert repr(formats) == "Gdk.ContentFormats(['text/plain', 'text/html'])"


def test_content_formats_new_for_gtype_and_parse() -> None:
    formats = Gdk.ContentFormats.new_for_gtype(str)
    parsed = Gdk.ContentFormats.parse("text/plain text/html")

    assert formats.get_gtypes()
    assert parsed is not None
    assert parsed.get_mime_types() == ["text/plain", "text/html"]


def probe_content_formats_union() -> list[str]:
    left = Gdk.ContentFormats.new(["text/plain", "text/html"])
    right = Gdk.ContentFormats.new(["text/uri-list"])
    union = left.union(right)
    return list(union.get_mime_types())


def test_content_formats_union_combines_mime_types() -> None:
    assert run_subprocess_probe(__file__, "probe_content_formats_union") == [
        "text/plain",
        "text/html",
        "text/uri-list",
    ]
