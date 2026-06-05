# API reference (auto-generated)

> The full goi API surface, generated from the GIR typelibs and goi overlays. This page is the entry point; per-namespace pages are generated alongside.

## What this chapter covers

- A roadmap of the generated namespaces: `GLib`, `Gio`, `GObject`, `Gdk`, `Gtk`, `Adw`, `Pango`, `Cairo`, `GdkPixbuf`, `GtkSource`, `WebKit`, `Soup`, more.
- How types, methods, signals, and properties are presented.
- Cross-links between the prose chapters and the API entries (every prose chapter links to API entries; every API entry can link back to the relevant chapter).
- Conventions: deprecated marks, since-version annotations, "this is a goi overlay" marks.

## Generation pipeline (notes for the maintainer)

- mkdocstrings + a custom handler reading the GIR XML and goi overlay metadata.
- mkdocs-gen-files / mkdocs-literate-nav to synthesize per-namespace pages.
- A small script in `scripts/docs/` that:
    - Walks installed typelibs.
    - Emits one `.md` per namespace under `reference/api/`.
    - Cross-links overlays (`goi/overlays/<Namespace>/...`) where they patch or replace upstream methods.
    - Adds anchors compatible with the C docs (`gtk_widget_set_visible` → matching anchor).

## What you'll be able to do

- Look up any class, method, signal, property by name.
- Jump from prose to API and back.

## Notes for the writer

- This page is a *stub* until the generation pipeline is wired up.
- Until then, link to upstream gtk.org docs as a fallback.
- The generation plumbing is itself a worthy small project — track it as a doc-tooling task.
