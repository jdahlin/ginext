# Blueprint

> A modern, readable language that compiles to GtkBuilder XML. The default for new GNOME apps — `.blp` source files, `blueprint-compiler` produces `.ui` files at build time.

## What this chapter covers

- Why Blueprint exists: `.ui` XML is verbose and hard to diff; Blueprint is closer to a real language.
- A 1:1 translation: the same dialog written in `.ui` XML and `.blp`, side by side.
- Syntax tour:
    - Object declarations, properties, child packing.
    - Templates (`template MyWindow : Adw.ApplicationWindow { ... }`).
    - Signal handlers.
    - Bindings (`bind`, `bind-property`).
    - Menus.
    - Inline expressions and references.
- Build integration: invoking `blueprint-compiler` from meson; outputs go into GResource.
- Editor support: language servers, syntax highlighting, formatters.
- Limits: what Blueprint can't express (rare), and the escape hatch (raw XML inclusion).
- Migration: porting an existing `.ui` codebase to Blueprint.

## What you'll be able to do

- Author UI in Blueprint comfortably.
- Convert existing `.ui` files to `.blp`.
- Wire Blueprint into a meson + GResource pipeline.

## Notes for the writer

- This is the modern default for GNOME apps. Pitch it confidently.
- Show the same composite template in raw XML and in Blueprint — the contrast sells itself.
- Pair tightly with [Declarative UI](../building/declarative-ui.md) (which introduces the underlying concepts).
