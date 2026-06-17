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

"""Static / top-level namespace functions.

Top-level callables like GLib.get_user_name() have no implicit self.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def GoiBench() -> Any:
    from ginext import private

    try:
        private.require_namespace("GoiBench", "1.0")
    except ImportError:
        pytest.skip("GoiBench typelib not available in this test environment")
    from ginext import GoiBench

    return GoiBench


def test_top_level_function_returns_value() -> None:
    from ginext import GLib

    assert isinstance(GLib.get_user_name(), str)


def test_top_level_function_callable_twice() -> None:
    from ginext import GLib

    a = GLib.get_user_name()
    b = GLib.get_user_name()
    assert a == b


def test_top_level_function_repr() -> None:
    from ginext import GLib

    r = repr(GLib.get_user_name)
    assert "get_user_name" in r


def test_passing_self_to_top_level_function_raises() -> None:
    from ginext import GLib

    with pytest.raises(TypeError):
        GLib.get_user_name(object())  # type: ignore[call-arg]  # tests that wrong-type arg raises TypeError


def test_top_level_function_is_cached_on_namespace() -> None:
    from ginext import GLib

    a = GLib.get_user_name
    b = GLib.get_user_name
    assert a is b


def test_goibench_trivial_int_functions_return_expected_values(GoiBench: Any) -> None:
    assert GoiBench.noop_int() == 0
    assert GoiBench.in_1_int(7) == 7
    assert GoiBench.in_2_int(7, 11) == 7
    assert GoiBench.in_6_int(1, 2, 3, 4, 5, 6) == 1


def test_goibench_bound_scalar_methods_return_expected_values(GoiBench: Any) -> None:
    obj = GoiBench.Object.new()

    assert obj.get_index() == 0
    obj.set_flag(True)
    obj.set_flag(False)
    assert type(obj).get_index(obj) == 0
    assert type(obj).set_flag(obj, True) is None


def test_goibench_bound_utf8_methods_return_expected_values(GoiBench: Any) -> None:
    obj = GoiBench.Object.new()

    obj.set_label("hi")
    assert obj.get_label() == "hi"
    assert type(obj).get_label(obj) == "hi"

    obj.set_label(None)
    assert obj.get_label() is None
    assert type(obj).set_label(obj, "bye") is None
    assert obj.get_label() == "bye"


def test_goibench_bound_object_return_methods_return_expected_values(
    GoiBench: Any,
) -> None:
    obj = GoiBench.Object.new()

    assert obj.lookup("undo") is obj
    assert obj.nth(0) is obj
    assert type(obj).lookup(obj, "undo") is obj
    assert type(obj).nth(obj, 0) is obj
