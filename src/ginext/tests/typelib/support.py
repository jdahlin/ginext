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

from ginext.namespace import Namespace


def open_namespace_for_test(call_mode: str, name: str, version: str = "1.0") -> Namespace:
    import ginext

    return ginext._load_namespace(name, version)


def is_ginext_wrapper(obj: object) -> bool:
    """True iff `obj`'s type was built by ginext's class builder.

    ginext installs `gimeta.gtype` on every GIR-derived heap type as a
    GType id marker, so its presence is a stable signal that we're
    looking at a ginext-managed wrapper without exposing the underlying
    `GObjectBase` plumbing as part of the public Python API."""
    return hasattr(type(obj), "gimeta")


def assert_gobject_class_mro(cls: type) -> None:
    """Assert that a GIR GObject class uses the live GObject.Object root."""
    import sys
    from ginext import GObject

    mro = cls.__mro__
    mro_ids = [(base.__module__, base.__qualname__, id(base)) for base in mro]
    root = GObject.Object
    root_identity = (root.__module__, root.__qualname__, id(root))
    module_state = {
        "ginext": id(sys.modules.get("ginext")),
        "ginext.GObject": id(sys.modules.get("ginext.GObject")),
    }

    assert root in mro, (
        f"{cls!r} MRO does not contain the live GObject.Object; "
        f"root={root_identity!r}, mro={mro_ids!r}, modules={module_state!r}"
    )
    assert issubclass(cls, root), (
        f"{cls!r} is not a subclass of the live GObject.Object; "
        f"root={root_identity!r}, mro={mro_ids!r}, modules={module_state!r}"
    )


def is_ginext_weakref(obj: object) -> bool:
    """True iff `obj` is a ginext GObjectWeakRef. The internal type is no
    longer exposed at module level, so tests check by class name. The
    repr-style identity is stable across ginext versions because the
    wrapper is named in C as `ginext.GObjectWeakRef`."""
    t = type(obj)
    return t.__name__ == "GObjectWeakRef" and t.__module__.startswith("ginext")
