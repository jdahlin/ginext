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

"""Port of goi/tests/test_pyargs_oracle.py.

Verifies the exact TypeError messages that CPython's PyArg_ParseTuple
produces for each numeric/string format code when given a wrong-type
argument.  ginext's C argument-checking code relies on these messages
matching what callers see; this test documents the contract.

The helpers live in ginext.private (not _testcapi) so the suite runs on
release builds without requiring Py_DEBUG.
"""

from __future__ import annotations

import pytest


PYARG_TEMPLATES = [
    ("b", "x", "'str' object cannot be interpreted as an integer"),
    ("B", "x", "'str' object cannot be interpreted as an integer"),
    ("h", "x", "'str' object cannot be interpreted as an integer"),
    ("H", "x", "'str' object cannot be interpreted as an integer"),
    ("i", "x", "'str' object cannot be interpreted as an integer"),
    ("I", "x", "'str' object cannot be interpreted as an integer"),
    ("l", "x", "'str' object cannot be interpreted as an integer"),
    ("L", "x", "'str' object cannot be interpreted as an integer"),
    ("n", "x", "'str' object cannot be interpreted as an integer"),
    ("k", "x", "argument 1 must be int, not str"),
    ("K", "x", "argument 1 must be int, not str"),
    ("f", "x", "must be real number, not str"),
    ("d", "x", "must be real number, not str"),
    ("s", 5, "argument 1 must be str, not int"),
]


@pytest.mark.parametrize(
    ("fmt", "bad", "expected"),
    PYARG_TEMPLATES,
    ids=[template[0] for template in PYARG_TEMPLATES],
)
def test_pyargs_template(fmt: str, bad: object, expected: str) -> None:
    from ginext import private

    fn = getattr(private, f"getargs_{fmt}")
    with pytest.raises(TypeError) as exc_info:
        fn(bad)
    assert str(exc_info.value) == expected
