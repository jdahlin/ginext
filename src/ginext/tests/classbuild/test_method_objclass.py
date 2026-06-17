# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from typing import Protocol, TypeGuard


class HasObjclass(Protocol):
    __objclass__: type[object]


def _has_objclass(method: object) -> TypeGuard[HasObjclass]:
    from ginext import Gio
    from ginext.method import GICallable

    return isinstance(method, (type(Gio.Cancellable.cancel), GICallable))


def test_imported_method_descriptors_expose_objclass() -> None:
    from ginext import Gio
    from ginext import Gtk

    cancellable_cancel = Gio.Cancellable.cancel
    file_copy = Gio.File.copy
    builder_add_from_string = Gtk.Builder.add_from_string

    assert _has_objclass(cancellable_cancel)
    assert _has_objclass(file_copy)
    assert _has_objclass(builder_add_from_string)

    assert cancellable_cancel.__objclass__ is Gio.Cancellable
    assert file_copy.__objclass__ is Gio.File
    assert builder_add_from_string.__objclass__ is Gtk.Builder
