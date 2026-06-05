# Actions and menus

> Modern GTK apps are built around **actions**: named, addressable commands that can be invoked from menus, shortcuts, buttons, the shell, or DBus — all without each invocation knowing about the others.

## What this chapter covers

- Why actions: decoupling "what" from "how it was triggered."
- `Gio.SimpleAction`: name, optional parameter type, optional state.
- Action scopes: app actions (`app.quit`) vs window actions (`win.close`) vs widget actions.
- Adding actions to an `ActionMap` (`Gtk.Application`, `Gtk.ApplicationWindow`, `Gtk.Widget` via `install_action`).
- Parameterized actions: passing a `GVariant`, e.g. `app.open-recent` with a file path.
- Stateful actions: toggles (boolean state) and radio groups (string state).
- Invoking actions: from code (`activate_action`), from menus, from shortcuts, from DBus.
- `Gio.Menu` and `Gio.MenuItem`: building menu trees in code.
- Menu models from `.ui` XML and from Blueprint.
- Wiring menus to UI: `Gtk.MenuButton`, the primary menu pattern, headerbar menus.
- App menu conventions (Help, About, Preferences, Quit).

## What you'll be able to do

- Build a complete app menu wired to actions, with keyboard shortcuts.
- Add per-widget actions (e.g., a "delete" action on a list row) without coupling.
- Trigger your app's actions from DBus / scripts.

## Notes for the writer

- Pair tightly with [Shortcuts](shortcuts.md) and [Context menus](context-menus.md).
- Show menu construction in code *and* in `.ui` XML — readers will encounter both.
- Mention but defer the "actions in CSS" form (`action-name="app.foo"` attribute) to the templates chapter cross-reference.
