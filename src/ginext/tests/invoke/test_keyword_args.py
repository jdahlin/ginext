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

from __future__ import annotations

from typing import Any

import pytest


def test_function_accepts_all_keyword_arguments() -> None:
    from ginext import GLib

    result = GLib.uri_parse_params(
        params="a=1&b=2",
        length=-1,
        separators="&",
        flags=GLib.UriParamsFlags.NONE,
    )

    assert result == {"a": "1", "b": "2"}


def test_function_accepts_mixed_keyword_arguments_out_of_order() -> None:
    from ginext import GLib

    result = GLib.uri_parse_params(
        "a=1&b=2",
        flags=GLib.UriParamsFlags.NONE,
        separators="&",
        length=-1,
    )

    assert result == {"a": "1", "b": "2"}


@pytest.mark.parametrize(
    ("args", "kwargs", "expected"),
    [
        (
            ("a=1",),
            {"params": "b=2", "length": -1, "separators": "&", "flags": 0},
            "uri_parse_params() got multiple values for keyword argument 'params'",
        ),
        (
            ("a=1",),
            {"length": -1, "separators": "&", "flags": 0, "unknown": 1},
            "uri_parse_params() got an unexpected keyword argument 'unknown'",
        ),
        (
            (),
            {"length": -1, "separators": "&", "flags": 0},
            "uri_parse_params() takes exactly 4 non-keyword arguments (0 given)",
        ),
        (
            ("a=1", -1, "&", 0, "extra"),
            {"flags": 0},
            "uri_parse_params() takes exactly 4 non-keyword arguments (5 given)",
        ),
    ],
    ids=["duplicate", "unknown", "gap", "too-many-positional-with-kw"],
)
def test_function_keyword_shape_errors(args: Any, kwargs: Any, expected: str) -> None:
    from ginext import GLib

    with pytest.raises(TypeError) as exc_info:
        GLib.uri_parse_params(*args, **kwargs)

    assert str(exc_info.value) == expected
