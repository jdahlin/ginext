# GTK ColumnView Ergonomics

`Gtk.ColumnView` is the modern GTK4 replacement for many old `Gtk.TreeView` and
`kiwi.ObjectList`-style use cases. The raw API is powerful, but it exposes all
of GTK's model/view plumbing directly:

```text
Gio.ListStore
-> Gtk.FilterListModel
-> Gtk.SortListModel
-> Gtk.SingleSelection / Gtk.MultiSelection / Gtk.NoSelection
-> Gtk.ColumnView
```

Each column also needs:

```text
Gtk.ColumnViewColumn
-> Gtk.SignalListItemFactory
-> setup/bind/unbind/teardown signal handlers
-> optional Gtk.Sorter
```

This is correct GTK, but it is too much boilerplate for the common Python case:
"show these objects with these columns, searchable, sortable, selectable".

## Raw API Today

A simplified raw setup looks like this:

```python
from goi.repository import Gio, GObject, Gtk


class FileRow(GObject.Object):
    # Assume GObject properties:
    # display_name: str
    # size_display: str
    # modified_display: str
    pass


store = Gio.ListStore.new(FileRow)
store.append(FileRow(display_name="a.txt", size_display="1 KB", modified_display="Today"))
store.append(FileRow(display_name="b.txt", size_display="2 KB", modified_display="Yesterday"))
```

Each text column needs a factory and usually a sorter:

```python
def make_text_column(title: str, prop: str) -> Gtk.ColumnViewColumn:
    factory = Gtk.SignalListItemFactory.new()

    def setup(factory, cell):
        label = Gtk.Label()
        label.set_xalign(0.0)
        cell.set_child(label)

    def bind(factory, cell):
        row = cell.get_item()
        label = cell.get_child()

        if row is None or label is None:
            return

        label.set_label(getattr(row, prop))

    factory.connect("setup", setup)
    factory.connect("bind", bind)

    column = Gtk.ColumnViewColumn.new(title, factory)

    expr = Gtk.PropertyExpression.new(FileRow, None, prop.replace("_", "-"))
    sorter = Gtk.StringSorter.new(expr)
    column.set_sorter(sorter)

    return column
```

Search is another model layer:

```python
search_expr = Gtk.PropertyExpression.new(FileRow, None, "display-name")

string_filter = Gtk.StringFilter.new(search_expr)
string_filter.set_ignore_case(True)
string_filter.set_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
string_filter.set_search("")

filtered = Gtk.FilterListModel.new(store, string_filter)
filtered.set_watch_items(True)
```

Sorting needs the special sorter owned by the view:

```python
view = Gtk.ColumnView.new(None)

name_column = make_text_column("Name", "display_name")
size_column = make_text_column("Size", "size_display")
modified_column = make_text_column("Modified", "modified_display")

view.append_column(name_column)
view.append_column(size_column)
view.append_column(modified_column)

sorter = view.get_sorter()
sorted_model = Gtk.SortListModel.new(filtered, sorter)
```

Selection wraps the final model:

```python
selection = Gtk.MultiSelection.new(sorted_model)
# or Gtk.SingleSelection.new(sorted_model)
# or Gtk.NoSelection.new(sorted_model)

view.set_model(selection)
```

Search entry changes must update the filter manually:

```python
search_entry = Gtk.SearchEntry()


def on_search_changed(entry):
    string_filter.set_search(entry.get_text())


search_entry.connect("search-changed", on_search_changed)
```

Initial sorting is separate:

```python
view.sort_by_column(name_column, Gtk.SortType.ASCENDING)
```

And the widget usually goes in a scroller:

```python
scroller = Gtk.ScrolledWindow()
scroller.set_child(view)
```

## Problem

The raw API requires the user to understand:

- `Gio.ListModel` item types;
- `Gtk.ColumnViewColumn` versus `Gtk.ColumnViewCell`;
- list item factory setup/bind lifetimes;
- expression construction;
- string filters and filter models;
- column sorters and the special `ColumnView.get_sorter()`;
- selection models;
- the correct order of wrapping models.

That is reasonable for GTK internals, but it is not the right first experience
for Python application code.

## Do Not Hide Raw GTK

ABI2 should keep the raw GTK API available:

```python
Gtk.ColumnView.new(selection_model)
Gtk.ColumnViewColumn.new("Name", factory)
Gtk.SignalListItemFactory.new()
Gtk.FilterListModel.new(model, filter)
Gtk.SortListModel.new(model, sorter)
```

The question is whether Python convenience should be added directly to
`Gtk.ColumnView` or first prototyped separately.

## GtkExtras Direction

Prototype the higher-level API in `GtkExtras` rather than immediately
overloading `Gtk.ColumnView`.

```python
from goi import Gtk, GtkExtras


view = GtkExtras.ColumnView(
    rows,
    columns=[
        GtkExtras.Column("Name", "display_name", expand=True),
        GtkExtras.Column("Size", "size_display", align="end"),
        GtkExtras.Column("Modified", "modified_display"),
    ],
    selection="multiple",
    search="display_name",
    sort="display_name",
)
```

This keeps the distinction clear:

- `Gtk.ColumnView` is the upstream GTK widget.
- `GtkExtras.ColumnView` is a Python convenience wrapper/builder.
- Stable pieces can later graduate into ABI2 overlays if they prove correct.

## Why GtkExtras

`GtkExtras` avoids committing too early to a core ABI2 surface:

- It makes the convenience layer explicitly Python-specific.
- It avoids surprising users who expect `Gtk.ColumnView` to match GTK docs.
- It allows faster iteration in examples such as `examples/commander`.
- It provides a place for opinionated helpers without polluting `Gtk`.
- It can still return or subclass real GTK widgets.

Do not let `GtkExtras` become a generic utility dump. Keep it focused on modern
GTK model/view ergonomics.

Initial scope:

```python
GtkExtras.Column
GtkExtras.ColumnView
GtkExtras.DropDown
GtkExtras.Expression
GtkExtras.item_factory
```

## Column Description

`GtkExtras.Column` should describe one visible column and expand into:

```text
Gtk.ColumnViewColumn
Gtk.SignalListItemFactory
Gtk.StringSorter or custom sorter
```

Proposed shape:

```python
GtkExtras.Column(
    title: str,
    expression,
    *,
    widget=None,
    sort=True,
    expand=False,
    resizable=True,
    visible=True,
    align=None,
    width=None,
    id=None,
)
```

Examples:

```python
GtkExtras.Column("Name", "display_name", expand=True)
GtkExtras.Column("Size", "size_display", align="end")
GtkExtras.Column("Modified", lambda row: row.modified_display)
GtkExtras.Column("Icon", "icon", widget=Gtk.Image)
```

The `expression` argument should follow the expression mapping in
`docs/internals/gtk-expression.md`:

- string means property path;
- simple lambda may compile to `Gtk.PropertyExpression`;
- formatting lambda maps to `Gtk.ClosureExpression`;
- explicit `Gtk.Expression` is used as-is.

## Search

Search should be optional and should build:

```text
Gtk.StringFilter
Gtk.FilterListModel
Gtk.SearchEntry connection or external search binding
```

Possible API:

```python
GtkExtras.ColumnView(rows, columns, search="display_name")
GtkExtras.ColumnView(rows, columns, search=search_entry)
GtkExtras.ColumnView(rows, columns, search=("display_name", search_entry))
```

Be careful with tuple/list shorthand. `docs/internals/gtk-expression.md` recommends not
using raw sequences for expression fallback. If multiple searchable fields are
needed, prefer explicit expression/filter composition:

```python
GtkExtras.Search("display_name", entry=search_entry)
GtkExtras.Search(Gtk.TryExpression("display_name", "name"), entry=search_entry)
```

or defer multi-field search until the single-field API is proven.

## Sort

Column header sorting should use real GTK column sorters:

```text
Gtk.ColumnViewColumn.set_sorter(...)
Gtk.ColumnView.get_sorter()
Gtk.SortListModel.new(filtered_model, view.get_sorter())
```

Column definitions should create a sorter by default when the expression returns
a string:

```python
GtkExtras.Column("Name", "display_name", sort=True)
```

Explicit sorter options can be added later:

```python
GtkExtras.Column("Name", "display_name", sort="string")
GtkExtras.Column("Size", "size", sort="numeric")
GtkExtras.Column("Modified", "modified", sort=Gtk.CustomSorter(...))
```

The first slice should only support string sorting unless numeric sorter support
is already straightforward.

## Selection

`selection=` should choose the selection model:

```python
selection="none"      # Gtk.NoSelection
selection="single"    # Gtk.SingleSelection
selection="multiple"  # Gtk.MultiSelection
```

The wrapper should expose Pythonic accessors:

```python
view.selected_item
view.selected_items
view.selected_position
```

Raw access must still be available:

```python
view.gtk_view.get_model()
view.selection_model
```

## Activation

ColumnView supports item activation through its signals/actions. `GtkExtras`
should make the common case direct:

```python
@view.on_activate
async def open_file(row):
    await row.open()
```

or:

```python
view.connect_activate(open_file)
```

This should be a later slice after the basic rendering/search/sort/selection
pipeline works.

## Commander Target

`examples/commander` is a good integration target:

```python
files = GtkExtras.ColumnView(
    directory.entries,
    columns=[
        GtkExtras.Column("Name", "display_name", expand=True),
        GtkExtras.Column("Size", "size_display", align="end"),
        GtkExtras.Column("Modified", "modified_display"),
    ],
    selection="multiple",
    search="display_name",
    sort="display_name",
)
```

This is the user-facing goal. The implementation can still be entirely built on
raw GTK models, factories, filters, sorters, and selection models.

## Open Questions

- Should `GtkExtras.ColumnView` subclass `Gtk.ColumnView`, wrap one, or be a
  builder function returning `Gtk.ColumnView`?
- How should Python object rows be represented if they are not already
  `GObject.Object` instances?
- Should the first slice require GObject properties for all column expressions?
- How should callback-backed `Gtk.ClosureExpression` lifetimes be owned?
- Should `GtkExtras` live as `goi.GtkExtras`, `goi.gtk.extras`, or another
  namespace?

Initial recommendation: make `GtkExtras.ColumnView` a small Python wrapper that
owns a real `Gtk.ColumnView` and exposes it as the widget once the project's
widget subclassing/overlays story is settled. If direct subclassing is easy and
safe, returning a real `Gtk.ColumnView` subclass may be preferable.
