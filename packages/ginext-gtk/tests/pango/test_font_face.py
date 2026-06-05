# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_family_with_faces


def test_font_face_exposes_name_description_and_family() -> None:
    family = make_family_with_faces()
    face = family.list_faces()[0]

    assert face.get_face_name()
    assert face.describe().get_family() == family.get_name()
    assert face.get_family() is family
    assert isinstance(face.is_synthesized(), bool)
    assert isinstance(face.list_sizes(), list)
