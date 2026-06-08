# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations


def test_list_model_wrappers_support_class_getitem(
    require_gtk4_display: object,
) -> None:
    _ = require_gtk4_display
    from ginext import Gtk

    selection_model_type: type[Gtk.SelectionModel[Gtk.StringObject]] = (
        Gtk.SelectionModel[Gtk.StringObject]
    )
    section_model_type: type[Gtk.SectionModel[Gtk.StringObject]] = (
        Gtk.SectionModel[Gtk.StringObject]
    )
    single_selection_type: type[Gtk.SingleSelection[Gtk.StringObject]] = (
        Gtk.SingleSelection[Gtk.StringObject]
    )
    multi_selection_type: type[Gtk.MultiSelection[Gtk.StringObject]] = (
        Gtk.MultiSelection[Gtk.StringObject]
    )
    no_selection_type: type[Gtk.NoSelection[Gtk.StringObject]] = (
        Gtk.NoSelection[Gtk.StringObject]
    )
    filter_list_model_type: type[Gtk.FilterListModel[Gtk.StringObject]] = (
        Gtk.FilterListModel[Gtk.StringObject]
    )

    assert selection_model_type is Gtk.SelectionModel
    assert section_model_type is Gtk.SectionModel
    assert single_selection_type is Gtk.SingleSelection
    assert multi_selection_type is Gtk.MultiSelection
    assert no_selection_type is Gtk.NoSelection
    assert filter_list_model_type is Gtk.FilterListModel


def test_selection_model_interfaces_expose_list_model_protocol(
    require_gtk4_display: object,
) -> None:
    _ = require_gtk4_display
    from ginext import Gtk

    stack = Gtk.Stack()
    stack.add_named(Gtk.Label(label="One"), "one")
    pages: Gtk.SelectionModel[Gtk.StackPage] = stack.get_pages()
    first_page: Gtk.StackPage = pages[0]

    assert len(pages) == 1
    assert list(pages) == [first_page]
