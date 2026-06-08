# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations


def test_list_model_family_supports_class_getitem() -> None:
    from ginext import Gio
    from ginext import GObject

    list_model_type: type[Gio.ListModel[GObject.Object]] = Gio.ListModel[GObject.Object]
    list_store_type: type[Gio.ListStore[GObject.Object]] = Gio.ListStore[GObject.Object]

    assert list_model_type is Gio.ListModel
    assert list_store_type is Gio.ListStore
