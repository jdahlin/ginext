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

from __future__ import annotations

import pytest

try:
    from ginext import Gee
except ImportError:
    # libgee / its typelib is not available on every platform (e.g. Windows).
    pytest.skip("Gee (libgee) namespace not available", allow_module_level=True)

from ginext.gobject.gtype import GType
from ginext import private


def test_gee_hash_set_constructor_callback_triples_build_and_invoke() -> None:
    kind, info = private.namespace_find("Gee", "0.8", "HashSet")
    assert kind == "object"

    data = info.object_info()
    constructor = next(
        method for method in data["methods"] if method.get_name() == "new"
    )

    descriptor = private.build_callable_descriptor(
        constructor, "Gee.HashSet.new", False
    )

    obj = private.invoke_callable_descriptor(
        descriptor,
        (
            GType.STRING,
            None,
            None,
            lambda *args: 0,
            lambda *args: True,
        ),
        None,
    )
    assert isinstance(obj, Gee.HashSet)


def test_gee_hash_set_class_identity_is_process_wide() -> None:
    from ginext.namespace import Namespace

    other_gee = Namespace("Gee", "0.8")
    assert other_gee.HashSet is Gee.HashSet
