# Widgets and layout

> How to put things on screen and arrange them. GTK's layout system is composable containers, not a constraint solver — once you know the half-dozen layout widgets you'll need every day, the rest is just naming.

## What this chapter covers

- The widget concept: every visible thing is a `Gtk.Widget`; widgets have parents and children.
- The properties that drive layout: `hexpand`/`vexpand`, `halign`/`valign`, `margin-*`, `width-request`/`height-request`.
- Layout containers (one section each, with one short example):
    - `Gtk.Box` — the workhorse, horizontal or vertical.
    - `Gtk.Grid` — when you need rows *and* columns.
    - `Gtk.CenterBox` — start/center/end.
    - `Gtk.Stack` — show one of several children; pair with `Gtk.StackSwitcher`/`StackSidebar`.
    - `Gtk.Paned` — resizable splitter.
    - `Gtk.Overlay` — stack widgets on top of each other.
    - `Gtk.Fixed` — when you really do want absolute positioning (rare).
    - `Gtk.Frame`, `Gtk.AspectFrame` — for the niche cases.
- Headerbars and window chrome (`Gtk.HeaderBar`, `Gtk.WindowControls`).
- Scrolled windows: when you need them, why they're not implicit.
- Common pitfalls: forgetting `hexpand`, mixing alignment with expand, fighting the natural size of children.

## What you'll be able to do

- Build the layout for a typical app window without reaching for tutorials.
- Recognize which container is appropriate for a given visual intent.
- Diagnose "why isn't my widget filling the space" / "why is everything tiny" from first principles.

## Notes for the writer

- Use real screenshots of each container with three children, so readers see the visual differences side by side.
- Avoid `Gtk.Fixed` examples that don't include a strong "you almost never want this" warning.
- Forward-link to libadwaita layout widgets in Part IV (`Adw.Clamp`, `Adw.Bin`, etc.) but don't introduce them here.
