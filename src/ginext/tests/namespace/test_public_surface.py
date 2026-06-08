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

"""Public-surface containment.

The plan explicitly forbids exposing:
- repository / open_namespace / require_version
- top-level base classes (no ginext.GObjectBase)
- info objects, method descriptors

All user API should be reached through a namespace object.
"""

from __future__ import annotations

from typing import cast

import pytest


@pytest.mark.parametrize(
    "name",
    [
        "repository",
        "open_namespace",
        "require_version",
        "Repository",
    ],
)
def test_no_repository_surface(name: str) -> None:
    import ginext

    assert not hasattr(ginext, name), f"ginext.{name} must not be a public attribute"


@pytest.mark.parametrize(
    "name",
    [
        "GObjectBase",
        "ObjectBase",
        "BaseObject",
    ],
)
def test_no_top_level_base_classes(name: str) -> None:
    import ginext

    assert not hasattr(ginext, name)


def test_no_info_object_classes_at_top_level() -> None:
    """ObjectInfo, FunctionInfo, etc. are implementation, not public."""
    import ginext

    for name in dir(ginext):
        assert not name.endswith("Info"), (
            f"ginext.{name} looks like a GI info object — should be private"
        )


def test_base_classes_reached_through_namespace() -> None:
    """The documented spelling is class Foo(GObject.Object): ..."""
    from ginext import GObject

    # GObject.Object must exist and be a type usable as a base.
    assert isinstance(GObject.Object, type)


def test_gobject_namespace_exposes_signal_descriptor() -> None:
    from ginext import GObject
    from ginext.signal.descriptor import SignalDescriptor

    # GObject.Signal is the SignalDescriptor re-exported as Signal.
    # The stub uses different class names (TOML Signal vs inline SignalDescriptor).
    assert cast("object", GObject.Signal) is cast("object", SignalDescriptor)
    assert "Signal" in dir(GObject)


def test_imported_gobject_classes_do_not_expose_signal_descriptor() -> None:
    import ginext

    # GObject.Object is the single canonical base and carries Signal as the
    # root; every other imported class stays gated.
    if hasattr(ginext, "GstPlay"):
        assert not hasattr(ginext.GstPlay.Play, "Signal")
        assert "Signal" not in dir(ginext.GstPlay.Play)


def test_native_namespace_hides_gobject_value() -> None:
    from ginext import GObject

    assert not hasattr(GObject, "Value")
    assert "Value" not in dir(GObject)
    with pytest.raises(AttributeError):
        GObject.Value


def test_underscore_modules_not_in_all() -> None:
    import ginext

    public = getattr(ginext, "__all__", None)
    if public is None:
        pytest.skip("ginext does not define __all__")
    for name in public:
        assert not name.startswith("_"), f"__all__ should not export {name}"
