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

import gc
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..conftest import PSpecInfo


def test_nick_survives_source_string_gc(
    make_property_class: Any, pspec_info: Any
) -> None:
    nick = "n" + str(id(object()))
    cls = make_property_class(int, nick=nick)

    del nick
    gc.collect()

    info = pspec_info(cls.gimeta.pspecs["x"])
    assert info.nick.startswith("n")


def test_blurb_survives_source_string_gc(
    make_property_class: Any, pspec_info: Any
) -> None:
    blurb = "b" + str(id(object()))
    cls = make_property_class(int, blurb=blurb)

    del blurb
    gc.collect()

    info = pspec_info(cls.gimeta.pspecs["x"])
    assert info.blurb.startswith("b")


def test_string_default_survives_source_gc(
    make_property_class: Any, pspec_default: Any
) -> None:
    default = "d" + str(id(object()))
    cls = make_property_class(str, default=default)

    expected = default
    del default
    gc.collect()

    assert pspec_default(cls.gimeta.pspecs["x"]) == expected


def test_class_survives_outliving_instances(
    GObject: Any, Property: Any, pspec_info: Any
) -> None:
    def make() -> Any:
        class Foo(GObject):  # type: ignore[misc]
            x: int = Property(default=42)

        return Foo

    cls = make()
    gc.collect()
    info: PSpecInfo = pspec_info(cls.gimeta.pspecs["x"])
    assert info.name == "x"
