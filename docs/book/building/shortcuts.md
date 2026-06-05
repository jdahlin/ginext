# Keyboard, accelerators, shortcuts

> How keys turn into actions. GTK has three layers worth knowing: per-widget shortcut controllers, app-wide accelerators tied to actions, and the GTK4 ShortcutController/Shortcut object model.

## What this chapter covers

- The unified model: `Gtk.Shortcut` = trigger + action; controllers hold sets of shortcuts.
- App-level accelerators via `Gtk.Application.set_accels_for_action()` — the simplest path for menu items.
- `Gtk.ShortcutController` on individual widgets, for context-sensitive bindings.
- Triggers (`Gtk.KeyvalTrigger`, `Gtk.MnemonicTrigger`, `Gtk.AlternativeTrigger`).
- Actions in shortcuts (`Gtk.NamedAction`, `Gtk.CallbackAction`, `Gtk.ActivateAction`, `Gtk.SignalAction`).
- The `Gtk.ShortcutsWindow` (the discoverable help overlay).
- Conventions: which keys are reserved by the platform, which by toolkits, and how to play nice.
- Mnemonics (`_File`) in labels and buttons.

## What you'll be able to do

- Bind keyboard shortcuts to app actions and to widget-level behavior.
- Build a discoverable shortcuts help window.
- Recognize key conflicts before users do.

## Notes for the writer

- Pair this with [Actions and menus](actions-and-menus.md); they're best read together.
- Include a table of platform-conventional shortcuts (Ctrl-N, Ctrl-W, F1, F11…) and which actions they map to.
