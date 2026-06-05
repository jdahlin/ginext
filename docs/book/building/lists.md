# Lists, columns, and grids

> GTK4 retired the GTK3 `TreeView` / `TreeModel` world in favor of `Gio.ListModel` + factory-based views. This chapter teaches the modern way: scalable, type-safe, and Pythonic.

## What this chapter covers

- The split: **list models** hold data, **factories** turn each item into a widget, **views** combine the two.
- The view widgets:
    - `Gtk.ListView` — single column.
    - `Gtk.ColumnView` — multiple columns with sortable headers.
    - `Gtk.GridView` — tile-style grid (photo grids, icon views).
- `Gio.ListModel`: the protocol — `get_item_type`, `get_n_items`, `get_item`, `items-changed`.
- Built-in models:
    - `Gio.ListStore` — your everyday mutable store.
    - `Gtk.StringList` — strings only.
    - `Gtk.FilterListModel`, `Gtk.SortListModel`, `Gtk.SliceListModel`, `Gtk.MultiSelection`, `Gtk.SingleSelection` — composable wrappers.
    - `Gtk.TreeListModel` — for hierarchical / tree data.
- `Gtk.SignalListItemFactory` vs `Gtk.BuilderListItemFactory` (template-based).
- The recycling lifecycle: `setup`, `bind`, `unbind`, `teardown`. What goes in each.
- Selection: `SingleSelection`, `MultiSelection`, `NoSelection`.
- Sorting: `Gtk.Sorter` and friends (custom sorters, multi-column).
- Filtering: `Gtk.Filter`, `Gtk.CustomFilter`, `Gtk.StringFilter`.
- Sections (group headers in `ListView`).
- Trees with `Gtk.TreeListModel`: building hierarchies on top of a flat model.
- Performance: virtualization, large data sets, expensive bind functions.

## What you'll be able to do

- Build a list/column/grid view from a Python data source.
- Add sorting, filtering, multi-selection.
- Migrate a GTK3 `TreeView` to the modern factory model.

## Notes for the writer

- This is the longest chapter in Part II — readers will reference it constantly.
- Show one **complete** worked example: a list of dataclasses with sort, filter, and a context menu.
- Cross-link to [Context menus](context-menus.md) and [Actions and menus](actions-and-menus.md).
- For tree-style data, show both the flat-model approach and `TreeListModel`.
