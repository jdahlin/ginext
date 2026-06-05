# Migration from PyGObject

> PyGObject is the older, widely-used GObject-Introspection binding for Python. goi is a newer, type-stub-rich alternative. Most of your knowledge transfers; some specifics don't.

## What stays the same

- The libraries you call (`Gtk`, `Gio`, `GLib`, `Adw`, `Pango`, `Cairo`…) and almost all of their public API.
- The `from goi.repository import Gtk` import style mirrors `from gi.repository import Gtk` — many files port with a single search-and-replace at the import line.
- `Gtk.Application`, signals, properties, templates, GResources, CSS — all work the same way.

## What's different

- **Import path**: `goi.repository` vs `gi.repository`. (No `gi.require_version` call — goi resolves typelibs differently.)
- **Type stubs**: goi ships precise stubs out of the box, so IDE autocomplete and pyright actually work without third-party stub packages.
- **Overlays**: goi has a documented `overlays/` mechanism for Pythonifying rough edges; PyGObject hides this inside the binding.
- **Async**: native `await` integration for `_async`/`_finish` GIO methods.
- **Construction shortcuts**: goi handles some kwarg patterns and convenience constructors that PyGObject doesn't.
- **Performance characteristics**: different hot paths; benchmarks are part of the project.

## What to watch out for when porting

- Custom `GObject` subclasses with `__gtype_name__` work the same; double-check property and signal declarations compile.
- Templates (`@Gtk.Template`): syntax is the same but cross-reference the [Declarative UI](../building/declarative-ui.md) chapter for current decorators.
- Anything that relied on PyGObject's `__gsignals__` dict style — confirm the goi form.
- C extensions you wrote against PyGObject's API: those don't carry over directly; see [Extending goi](../extending/index.md).

## Worked example

Port a small PyGObject app from the `apps/` directory (one that hasn't yet been migrated) and call out every change.

## Notes for the writer

- Be respectful of PyGObject — it shipped GNOME for a decade. The case for goi is not that PyGObject is bad, it's that goi trades different tradeoffs.
- Maintain a running list of common port issues that emerge from the `apps/` ports — this is the most useful artifact in this guide.
