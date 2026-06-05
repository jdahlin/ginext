# Declarative UI: Builder, Templates, GResource

> Writing UI in Python works, but real apps describe their UI in XML and load it at runtime — for clarity, hot-reload, and translatable strings. This chapter covers `GtkBuilder`, composite templates, and bundling assets with GResource.

## What this chapter covers

- The `.ui` XML format: objects, properties, child packing, signal connections.
- `Gtk.Builder` API: loading a `.ui` file, fetching objects by ID, connecting signals to handlers.
- **Composite templates**: a custom widget subclass whose contents are defined in XML.
    - `@Gtk.Template(filename=...)` and `@Gtk.Template(resource_path=...)`.
    - `Gtk.Template.Child()` for accessing template children.
    - `Gtk.Template.Callback()` for signal handlers.
- GResource: compiling assets (UI, CSS, images) into a binary bundle.
    - `gresource.xml` manifest.
    - `glib-compile-resources` and how to integrate with meson.
    - Loading the resource at startup and referring to assets by path.
- When to choose `.ui` files over Python construction, and vice versa.
- Blueprint as a more readable source for `.ui` files (forward link to Part IV).

## What you'll be able to do

- Author UI in `.ui` XML and load it at runtime.
- Build composite templates so each widget has its own file.
- Bundle UI, CSS, and icons into a GResource and ship a single binary asset.

## Notes for the writer

- This is one of the most consequential chapters in the book — almost every subsequent example uses templates.
- Show the same small widget three ways: pure Python, `.ui` + Builder, composite template. Then say which to use.
- Defer Blueprint to Part IV but mention it here so readers know it exists.
