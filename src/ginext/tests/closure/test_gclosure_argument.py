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

"""GClosure as a function argument (ported from pygobject's TestGClosure).

Exercises the same `pygi_closure_new` / `pygi_closure_new_with_kind` paths
that signal connections use, but through a method that takes a `GClosure*`
argument instead. The marshal turns the Python callable into a
`PyGIPyClosure` and the C side invokes it via `g_closure_invoke`.
"""

from __future__ import annotations

from functools import partial
from typing import Any

import pytest

from ..typelib.support import open_namespace_for_test


@pytest.fixture
def t() -> Any:
    return open_namespace_for_test("ginext", "GIMarshallingTests", "1.0")


def test_lambda_callable(t: Any) -> None:
    """A plain Python lambda passes the GClosure argument check and is
    invoked by the C side."""
    assert t.gclosure_in(lambda: 42) is None


def test_partial_forwards_bound_arguments(t: Any) -> None:
    """functools.partial wrapping a callable should bind its captured
    args/kwargs and still be invoked through the GClosure marshal."""
    called_args: list[Any] = []
    called_kwargs: dict[str, Any] = {}

    def callback(*args: Any, **kwargs: Any) -> int:
        called_args.extend(args)
        called_kwargs.update(kwargs)
        return 42

    func = partial(callback, 1, 2, 3, foo=42)
    t.gclosure_in(func)
    assert called_args == [1, 2, 3]
    assert called_kwargs["foo"] == 42


def test_closure_passes_through(t: Any) -> None:
    """A GClosure returned by one GI call should be acceptable as input to
    another GI call expecting a GClosure."""
    closure = t.gclosure_return()
    assert closure is not None
    assert t.gclosure_in(closure) is None


def test_non_callable_int_rejected(t: Any) -> None:
    with pytest.raises(TypeError):
        t.gclosure_in(42)


def test_non_callable_none_rejected(t: Any) -> None:
    with pytest.raises(TypeError):
        t.gclosure_in(None)
