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

from typing import Any, cast

import pytest

from ..typelib.support import open_namespace_for_test


@pytest.fixture
def gi_marshalling_tests(call_mode: Any) -> Any:
    return open_namespace_for_test(call_mode, "GIMarshallingTests", "1.0")


def test_type_name(GType: Any) -> None:
    from ginext import GObject

    assert GObject.type_name(GType.OBJECT.gimeta.gtype) == "GObject"


def test_type_from_name(GType: Any) -> None:
    from ginext import GObject

    assert GObject.type_from_name("GObject") == GType.OBJECT.gimeta.gtype
    assert GObject.type_from_name("!NOT_A_REAL_TYPE!") == 0


def test_type_is_a(GObject: Any, GType: Any, unique_type_name: Any) -> None:
    from ginext import GObject as GObjectNamespace

    class CustomBase(GObject, type_name=unique_type_name("PygCustomBase")):  # type: ignore[misc, call-arg]
        pass

    class CustomChild(CustomBase, type_name=unique_type_name("PygCustomChild")):  # type: ignore[call-arg]
        pass

    assert GObjectNamespace.type_is_a(CustomBase, GType.OBJECT.gimeta.gtype) is True
    assert GObjectNamespace.type_is_a(CustomChild, CustomBase) is True
    assert (
        GObjectNamespace.type_is_a(
            CustomBase.gimeta.gtype,
            GType.OBJECT.gimeta.gtype,
        )
        is True
    )
    assert GObjectNamespace.type_is_a(GType.OBJECT.gimeta.gtype, CustomBase) is False


def test_type_children(GObject: Any, unique_type_name: Any) -> None:
    from ginext import GObject as GObjectNamespace

    class CustomBase(GObject, type_name=unique_type_name("PygParent")):  # type: ignore[misc, call-arg]
        pass

    class CustomChild(CustomBase, type_name=unique_type_name("PygChild")):  # type: ignore[call-arg]
        pass

    assert GObjectNamespace.type_children(CustomBase.gimeta.gtype) == [
        CustomChild.gimeta.gtype
    ]
    assert GObjectNamespace.type_children(CustomChild.gimeta.gtype) == []


def test_type_interfaces(GObject: Any, unique_type_name: Any) -> None:
    from ginext import GObject as GObjectNamespace

    class CustomBase(GObject, type_name=unique_type_name("PygIfaceBase")):  # type: ignore[misc, call-arg]
        pass

    assert GObjectNamespace.type_interfaces(CustomBase.gimeta.gtype) == []


def test_type_interfaces_reports_declared_interface(
    GObject: type[object], gi_marshalling_tests: Any, unique_type_name: Any
) -> None:
    from ginext import GObject as GObjectNamespace

    CustomChild = type(GObject)(  # type: ignore[misc]
        "CustomChild",
        (GObject, cast("type[object]", gi_marshalling_tests.Interface)),
        {},
        type_name=unique_type_name("PygIfaceChild"),
    )

    assert GObjectNamespace.type_interfaces(CustomChild.gimeta.gtype) == [
        gi_marshalling_tests.Interface.gimeta.gtype
    ]


def test_python_defined_interface_impl_dispatches_vfunc(
    GObject: type[object], gi_marshalling_tests: Any, unique_type_name: Any
) -> None:
    def __init__(self: Any) -> None:
        super(type(self), self).__init__()
        self.val = None

    def do_test_int8_in(self: Any, int8: int) -> None:
        self.val = int8

    CustomImpl = type(GObject)(  # type: ignore[misc]
        "CustomImpl",
        (GObject, cast("type[object]", gi_marshalling_tests.Interface)),
        {"__init__": __init__, "do_test_int8_in": do_test_int8_in},
        type_name=unique_type_name("PygIfaceImpl"),
    )

    impl = CustomImpl()
    assert isinstance(impl, gi_marshalling_tests.Interface)
    gi_marshalling_tests.test_interface_test_int8_in(impl, 42)
    assert impl.val == 42


def test_type_parent(GObject: Any, GType: Any, unique_type_name: Any) -> None:
    from ginext import GObject as GObjectNamespace

    class CustomBase(GObject, type_name=unique_type_name("PygParentBase")):  # type: ignore[misc, call-arg]
        pass

    class CustomChild(CustomBase, type_name=unique_type_name("PygParentChild")):  # type: ignore[call-arg]
        pass

    assert (
        GObjectNamespace.type_parent(CustomChild.gimeta.gtype)
        == CustomBase.gimeta.gtype
    )
    assert (
        GObjectNamespace.type_parent(CustomBase.gimeta.gtype)
        == GType.OBJECT.gimeta.gtype
    )
