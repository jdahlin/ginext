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

from .support import open_namespace_for_test


@pytest.fixture
def t(call_mode: Any) -> Any:
    return open_namespace_for_test(call_mode, "GIMarshallingTests", "1.0")


@pytest.mark.parametrize(
    ("args", "kwargs"),
    [
        ((), {"a": 1, "b": 2, "c": 3}),
        ((1,), {"b": 2, "c": 3}),
        ((1, 2), {"c": 3}),
        ((1,), {"c": 3, "b": 2}),
        ((), {"c": 3, "a": 1, "b": 2}),
    ],
    ids=["all-kw", "1-pos-2-kw", "2-pos-1-kw", "out-of-order-kw", "scrambled-kw"],
)
def test_kwargs_dispatch_to_gimarshallingtests(t: Any, args: Any, kwargs: Any) -> None:
    assert t.int_three_in_three_out(*args, **kwargs) == (1, 2, 3)


@pytest.mark.parametrize(
    ("args", "kwargs", "expected"),
    [
        (
            (),
            {"c": 3},
            "int_three_in_three_out() takes exactly 3 non-keyword arguments (0 given)",
        ),
        (
            (1, 2, 3, 4),
            {"c": 3},
            "int_three_in_three_out() takes exactly 3 non-keyword arguments (4 given)",
        ),
        (
            (1, 2, 3),
            {"a": 4, "b": 5},
            "int_three_in_three_out() got multiple values for keyword argument 'a'",
        ),
        (
            (),
            {"d": 4},
            "int_three_in_three_out() got an unexpected keyword argument 'd'",
        ),
    ],
    ids=["mixed-too-few", "mixed-too-many", "multiple-values", "unknown"],
)
def test_keyword_shape_errors_match_pyarg_templates(
    t: Any, args: Any, kwargs: Any, expected: str
) -> None:
    with pytest.raises(TypeError) as exc_info:
        t.int_three_in_three_out(*args, **kwargs)

    assert str(exc_info.value) == expected
