# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from ginext import Pango


def test_language_round_trips_and_reports_scripts() -> None:
    language = Pango.Language.from_string("en")

    assert language is not None
    assert language.to_string() == "en"
    assert str(language) == "en"
    assert repr(language) == "Pango.Language('en')"
    assert language.matches("en") is True
    assert language.get_sample_string()
    assert isinstance(language.get_scripts(), list)
    assert language.includes_script(Pango.Script.LATIN) is True


def test_language_default_and_preferred_are_available() -> None:
    default = Pango.Language.get_default()
    preferred = Pango.Language.get_preferred()

    assert default is not None
    assert default.to_string()
    assert preferred is None or isinstance(preferred, list)
