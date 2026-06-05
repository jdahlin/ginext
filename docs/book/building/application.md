# GtkApplication

> The object that owns your app's lifecycle: single-instance handling, command-line parsing, the action map, startup/activate/shutdown, and the main loop.

## What this chapter covers

- Why `Gtk.Application` exists and what it gives you over a raw `Gtk.Window`.
- The lifecycle signals: `startup`, `activate`, `open`, `shutdown` — when each fires and what to put in each.
- App ID conventions (reverse-DNS) and what depends on it (DBus name, GResource paths, settings schemas).
- Single-instance behavior: how the second invocation reaches the first.
- Application flags: `HANDLES_OPEN`, `HANDLES_COMMAND_LINE`, `NON_UNIQUE`, `IS_SERVICE`.
- Command-line handling: `command-line` signal, `handle-local-options`, GOption-style parsing.
- The action map: registering app-level actions readers will use in menus and shortcuts.
- Holding the application alive: `hold` / `release`.
- Inactivity timeout and `IS_SERVICE` apps.
- `Adw.Application` as the GNOME variant (forward link to Part IV).

## What you'll be able to do

- Structure a real app around `Gtk.Application` rather than ad-hoc top-level windows.
- Handle command-line invocations and file opens correctly.
- Register actions that menus, keyboard shortcuts, and other parts of the app can call uniformly.

## Notes for the writer

- This is one of the most reusable chapters — every other Part links here.
- Show a minimal `Gtk.Application` subclass and a function-style version; readers in the wild will see both.
- Distinguish app-level actions from window-level actions; this gets misused constantly.
