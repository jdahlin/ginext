# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from .support import make_transform


def test_transform_parses_and_reports_affine_components() -> None:
    from ginext import Gsk

    ok, parsed = Gsk.Transform.parse("translate(2,3)")
    assert ok is True
    assert parsed is not None
    assert parsed.equal(parsed) is True

    transform = make_transform()
    assert transform.to_string() == "translate(2, 3)"
    assert transform.get_category() == getattr(Gsk.TransformCategory, "2D_TRANSLATE")
    assert transform.to_translate() == (2.0, 3.0)
    assert transform.to_affine() == (1.0, 1.0, 2.0, 3.0)
    assert transform.to_2d() == (1.0, 0.0, 0.0, 1.0, 2.0, 3.0)
    assert transform.invert() is not None
    assert repr(transform) == "Gsk.Transform('translate(2, 3)')"


def test_translate_keeps_wrapper_alive_for_later_namespace_use() -> None:
    from ginext import Gtk

    transform = make_transform()

    assert transform.to_translate() == (2.0, 3.0)

    adjustment = Gtk.Adjustment()
    assert adjustment._is_floating_for_test() is False
