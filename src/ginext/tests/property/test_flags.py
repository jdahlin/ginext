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

from ..conftest import (
    PARAM_CONSTRUCT_ONLY,
    PARAM_READABLE,
    PARAM_READWRITE,
    PARAM_USER_MASK,
    PARAM_WRITABLE,
)


@pytest.mark.parametrize(
    "kwargs, expected_set, expected_clear, expected_user_mask",
    [
        pytest.param(
            {},
            [PARAM_READABLE, PARAM_WRITABLE],
            [PARAM_CONSTRUCT_ONLY],
            PARAM_READWRITE,
            id="default",
        ),
        pytest.param(
            {"readonly": True},
            [PARAM_READABLE],
            [PARAM_WRITABLE, PARAM_CONSTRUCT_ONLY],
            PARAM_READABLE,
            id="readonly",
        ),
        pytest.param(
            {"construct_only": True},
            [PARAM_READABLE, PARAM_WRITABLE, PARAM_CONSTRUCT_ONLY],
            [],
            PARAM_READWRITE | PARAM_CONSTRUCT_ONLY,
            id="construct-only",
        ),
    ],
)
def test_flag_matrix(
    make_property_class: Any,
    pspec_info: Any,
    kwargs: Any,
    expected_set: Any,
    expected_clear: Any,
    expected_user_mask: Any,
) -> None:
    cls = make_property_class(int, **kwargs)
    info = pspec_info(cls.gimeta.pspecs["x"])

    assert info.flags & PARAM_USER_MASK == expected_user_mask
    for flag in expected_set:
        assert info.has_flag(flag), (
            f"expected flag {flag:#x} to be set, got {info.flags:#x}"
        )
    for flag in expected_clear:
        assert not info.has_flag(flag), (
            f"expected flag {flag:#x} to be clear, got {info.flags:#x}"
        )


def test_readonly_and_construct_only_together(
    make_property_class: Any, pspec_info: Any
) -> None:
    cls = make_property_class(int, readonly=True, construct_only=True)
    info = pspec_info(cls.gimeta.pspecs["x"])
    assert info.has_flag(PARAM_READABLE)
    assert info.has_flag(PARAM_WRITABLE)
    assert info.has_flag(PARAM_CONSTRUCT_ONLY)
