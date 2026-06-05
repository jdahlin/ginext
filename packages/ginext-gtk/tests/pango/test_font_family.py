# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_family_with_faces


def test_font_family_exposes_name_faces_and_flags() -> None:
    family = make_family_with_faces()
    faces = family.list_faces()

    assert family.get_name()
    assert faces
    assert isinstance(family.is_monospace(), bool)
    assert isinstance(family.is_variable(), bool)
