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

"""End-to-end caching: second access of every layer returns the same
objects without re-walking GI metadata."""

from __future__ import annotations

import pytest


def test_namespace_class_method_all_cached() -> None:
    import ginext

    a_ns = ginext.GLib
    b_ns = ginext.GLib
    assert a_ns is b_ns

    a_fn = a_ns.get_user_name
    b_fn = b_ns.get_user_name
    assert a_fn is b_fn

    from ginext import Gio

    a_cls = Gio.Cancellable
    b_cls = Gio.Cancellable
    assert a_cls is b_cls

    a_method = a_cls.cancel
    b_method = b_cls.cancel
    assert a_method is b_method


@pytest.mark.subprocess(timeout=30)
def test_self_referential_build_is_idempotent_not_recursive() -> None:
    """Resolving GObject.Object runs its overlay install, which re-accesses
    GObject.Object *before* the build finishes (typelib-method install reaches
    back for the base class). The builder must register the class on the
    namespace (and re-export a gtype-cache hit) before running overlays, so the
    re-entrant lookup resolves to the in-progress class instead of rebuilding —
    rebuilding would re-enter overlay install and recurse without terminating.

    Runs in a fresh subprocess so GObject.Object is built cold (it is a process
    singleton cached thereafter); without the pre-overlay registration this
    raises RecursionError instead of resolving.
    """
    import ginext

    obj_cls = ginext.GObject.Object
    assert isinstance(obj_cls, type)
    # Idempotent: the re-entrant lookup during build returned the same object
    # that the outer resolution ultimately caches.
    assert obj_cls is ginext.GObject.Object
