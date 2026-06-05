# Debugging GTK apps

> The tools, tricks, and environment variables that turn "it's broken" into "it's broken because…"

## What this chapter covers

- The GTK Inspector (`GTK_DEBUG=interactive`, or Ctrl-Shift-D / Ctrl-Shift-I):
    - Walking the widget tree.
    - Live-editing properties.
    - The CSS console.
    - Object hierarchy and inheritance.
    - Action and shortcut inventories.
    - Recorder (frame-by-frame render nodes).
    - Magnifier and visual debugging.
- Environment variables that earn their keep:
    - `GTK_DEBUG` — flags include `interactive`, `actions`, `builder`, `keybindings`, `layout`, `tree`.
    - `GDK_DEBUG` — events, drawing, frames.
    - `GSK_DEBUG` — renderer, full-redraw, vulkan.
    - `G_MESSAGES_DEBUG` — `all`, `Gtk`, `Gdk`, `GLib-GObject`, etc.
    - `G_DEBUG=fatal-warnings` — turn warnings into traps under a debugger.
    - `GOBJECT_DEBUG=instance-count` — find object leaks.
- DBus inspection: `D-Spy`, `busctl`, `gdbus monitor`.
- Logging with `GLib.log_structured` and reading structured logs in journalctl.
- gdb attach with PyGI: which symbols you'll see, when to drop in.
- Reproducing user bugs: portable bug reports, anonymizing AppStream-collected info.
- Common bug categories and where to look:
    - "Why doesn't my widget appear?" → expand, allocation, parent visible.
    - "Why doesn't my signal fire?" → wrong object, wrong signal name, handler returned True.
    - "Why isn't my CSS applying?" → provider scope, priority, specificity.
    - "Why is my action greyed out?" → action scope, enable state, target type.

## What you'll be able to do

- Reach for the right tool in the first 30 seconds of "huh, that's weird."
- Diagnose the most common GTK bug shapes from the symptom.

## Notes for the writer

- This chapter is "tricks the docs don't have." Pull from your own painful debugging stories.
- One concrete walkthrough: "user reports a button stops working, we figure out why."
