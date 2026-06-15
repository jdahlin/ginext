# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

from typing import Any

import pytest

from ..conftest import BUILTIN_VALUE_TYPES


def test_explicit_nick_and_blurb(make_property_class: Any, pspec_info: Any) -> None:
    cls = make_property_class(
        str, name="title", nick="Title", blurb="The title of the thing"
    )
    info = pspec_info(cls.gimeta.pspecs["title"])
    assert info.nick == "Title"
    assert info.blurb == "The title of the thing"


def test_missing_nick_falls_back_to_name(
    make_property_class: Any, pspec_info: Any
) -> None:
    cls = make_property_class(str, name="title")
    info = pspec_info(cls.gimeta.pspecs["title"])
    assert info.nick == "title"


def test_missing_blurb_is_none(make_property_class: Any, pspec_info: Any) -> None:
    cls = make_property_class(str, name="title")
    info = pspec_info(cls.gimeta.pspecs["title"])
    assert info.blurb is None


def test_gimeta_repr_includes_type_name_and_property_count(
    make_property_class: Any,
) -> None:
    cls = make_property_class(int, name="count")
    actual = repr(cls.gimeta)

    assert cls.gimeta.type_name in actual
    assert "gtype=" in actual
    assert "n_pspecs=1" in actual


def test_gimeta_pspecs_is_snapshot(make_property_class: Any) -> None:
    cls = make_property_class(int, name="count")
    pspecs = cls.gimeta.pspecs
    original = pspecs["count"]

    pspecs["count"] = 0

    assert cls.gimeta.pspecs["count"] == original


def test_direct_gimeta_get_missing_property_raises(make_property_class: Any) -> None:
    cls = make_property_class(int)

    with pytest.raises(AttributeError, match="has no property missing"):
        cls.gimeta.get_property(cls(), "missing")


def test_direct_gimeta_set_missing_property_raises(make_property_class: Any) -> None:
    cls = make_property_class(int)

    with pytest.raises(AttributeError, match="has no property missing"):
        cls.gimeta.set_property(cls(), "missing", 1)


def test_direct_gimeta_get_null_gobject_pointer_raises(
    make_property_class: Any,
) -> None:
    cls = make_property_class(int)
    obj = cls.__new__(cls)

    with pytest.raises(AttributeError, match="wrapper is not bound"):
        cls.gimeta.get_property(obj, "x")


@pytest.mark.parametrize(
    "nick, blurb, expected_nick",
    [
        pytest.param("Just Nick", None, "Just Nick", id="nick-only"),
        pytest.param(None, "Just Blurb", "x", id="blurb-only"),
        pytest.param("Both", "Both Set", "Both", id="both"),
        pytest.param("", "", "", id="empty-strings"),
    ],
)
def test_nick_blurb_matrix(
    make_property_class: Any,
    pspec_info: Any,
    nick: Any,
    blurb: Any,
    expected_nick: Any,
) -> None:
    cls = make_property_class(int, nick=nick, blurb=blurb)
    info = pspec_info(cls.gimeta.pspecs["x"])
    assert info.nick == expected_nick
    assert info.blurb == blurb


@pytest.mark.parametrize(
    "py_name, wire_name",
    [
        pytest.param("simple", "simple", id="no-underscore"),
        pytest.param("one_underscore", "one-underscore", id="single-underscore"),
        pytest.param(
            "many_under_score_s", "many-under-score-s", id="multiple-underscores"
        ),
        pytest.param("trailing_", "trailing-", id="trailing-underscore"),
        pytest.param("a", "a", id="single-char"),
        pytest.param("abc123", "abc123", id="digit-in-middle"),
    ],
)
def test_name_canonicalization(
    make_subclass: Any,
    Property: Any,
    pspec_info: Any,
    py_name: Any,
    wire_name: Any,
) -> None:
    cls = make_subclass({py_name: (int, Property())}, prefix="Name")
    assert py_name in cls.gimeta.pspecs
    info = pspec_info(cls.gimeta.pspecs[py_name])
    assert info.name == wire_name


@pytest.mark.parametrize("case", BUILTIN_VALUE_TYPES)
def test_canonical_name_is_independent_of_value_type(
    make_property_class: Any, pspec_info: Any, case: Any
) -> None:
    cls = make_property_class(case.annotation, name="my_field")
    info = pspec_info(cls.gimeta.pspecs["my_field"])
    assert info.name == "my-field"


@pytest.mark.parametrize(
    "nick",
    [
        pytest.param("", id="empty"),
        pytest.param("a", id="single-char"),
        pytest.param("hello world", id="space"),
        pytest.param("ünïcödé", id="non-ascii"),
        pytest.param("中文", id="cjk"),
        pytest.param("with\nnewline", id="newline"),
        pytest.param("with\ttab", id="tab"),
        pytest.param("a" * 1000, id="very-long"),
    ],
)
def test_nick_round_trips_verbatim(
    make_property_class: Any, pspec_info: Any, nick: Any
) -> None:
    cls = make_property_class(int, nick=nick)
    info = pspec_info(cls.gimeta.pspecs["x"])
    assert info.nick == nick


@pytest.mark.parametrize(
    "blurb",
    [
        pytest.param("", id="empty"),
        pytest.param("Short.", id="short"),
        pytest.param("A " * 500 + "long one.", id="kilobyte-ish"),
        pytest.param("Line 1\nLine 2", id="multiline"),
        pytest.param("emoji: 🦀", id="emoji"),
    ],
)
def test_blurb_round_trips_verbatim(
    make_property_class: Any, pspec_info: Any, blurb: Any
) -> None:
    cls = make_property_class(int, blurb=blurb)
    info = pspec_info(cls.gimeta.pspecs["x"])
    assert info.blurb == blurb


def test_nick_with_embedded_null_byte_is_truncated_or_preserved(
    make_property_class: Any, pspec_info: Any
) -> None:
    cls = make_property_class(int, nick="ab\x00cd")
    info = pspec_info(cls.gimeta.pspecs["x"])
    assert info.nick in ("ab", "ab\x00cd")


@pytest.mark.parametrize("count", [50, 1000], ids=["many", "huge"])
def test_class_with_many_properties_all_register(
    make_subclass: Any, Property: Any, count: Any
) -> None:
    fields = {f"p{i}": (int, Property(default=i)) for i in range(count)}
    cls = make_subclass(fields, prefix="Many")
    assert len(cls.gimeta.pspecs) == count
    assert [cls.gimeta.prop_ids[f"p{i}"] for i in range(count)] == list(
        range(1, count + 1)
    )


def test_mixed_types_each_get_correct_value_type(
    make_subclass: Any, Property: Any, pspec_info: Any
) -> None:
    cls = make_subclass(
        {
            "a": (bool, Property()),
            "b": (int, Property()),
            "c": (float, Property()),
            "d": (str, Property()),
        },
        prefix="Mixed",
    )

    assert pspec_info(cls.gimeta.pspecs["a"]).value_type_name == "gboolean"
    assert pspec_info(cls.gimeta.pspecs["b"]).value_type_name == "gint64"
    assert pspec_info(cls.gimeta.pspecs["c"]).value_type_name == "gdouble"
    assert pspec_info(cls.gimeta.pspecs["d"]).value_type_name == "gchararray"
