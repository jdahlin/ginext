# GNOME Builder

> The IDE designed for GNOME app development. It's not mandatory, but it does a lot of work for you — integrated Flatpak runtime, template scaffolding, debugger, inspector — and the project layout it generates is the de-facto convention.

## What this chapter covers

- Installing Builder (Flathub).
- Project templates: GTK app, Adw app, library, command-line. What each generates.
- A tour of the generated project:
    - `meson.build` at root and in subdirectories.
    - `data/` (desktop file, metainfo, icons, GSettings schema, GResource manifest).
    - `src/` (main module, window, UI files, blueprint).
    - `po/` (translations).
    - Flatpak manifest (often `<app-id>.json` or `.yaml`).
- The Builder workflow: building inside the runtime, running, debugging, exporting a Flatpak bundle.
- Integrated inspector and structured logs.
- Editing `.ui` and `.blp` files (with previews where available).
- When *not* to use Builder: existing projects, headless dev setups, non-GNOME desktops.

## What you'll be able to do

- Generate a working GNOME app skeleton in two minutes.
- Use Builder's run/debug workflow.
- Read a Builder-generated project and know which files do what.

## Notes for the writer

- Don't tell readers Builder is required; many will use VS Code or vim and want recipes for that.
- The most useful artifact is a labeled diagram of the generated project structure.
