# AdwApplication and windows

> libadwaita's drop-in replacements for `Gtk.Application` and `Gtk.ApplicationWindow`. Same APIs, GNOME-appropriate defaults, the AdwStyleManager integration that makes light/dark and accent colors "just work."

## What this chapter covers

- `Adw.Application`: what it adds over `Gtk.Application` (style manager, conventional handlers).
- `Adw.ApplicationWindow`: the modern GNOME window shell. No separate `Gtk.HeaderBar`; content area is yours.
- `Adw.Window` (when you don't need the `Gio.ApplicationWindow` plumbing).
- The headerbar pattern in Adw: `Adw.HeaderBar`, embedding it via `Adw.ToolbarView`, multiple toolbars (top/bottom).
- Putting it together: `ToolbarView` with a headerbar at the top and a content area below.
- Menu button conventions in the headerbar.
- Window state restoration (size, maximized) via `GSettings`.

## What you'll be able to do

- Bootstrap a GNOME app shell that looks right and behaves predictably.
- Recognize the standard headerbar/content layout when reading other apps' source.

## Notes for the writer

- Short and recipe-shaped: one canonical "GNOME app skeleton" example readers can copy.
- Cross-link to the corresponding GTK chapter ([GtkApplication](../building/application.md)) since the lifecycle hooks are identical.
