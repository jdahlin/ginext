# Context menus

> Right-click menus, attached to widgets, built from menu models, wired through the action system. Short chapter that ties together [Events](events-and-input.md) and [Actions and menus](actions-and-menus.md).

## What this chapter covers

- `Gtk.PopoverMenu` from a `Gio.MenuModel`.
- Triggering on secondary click via `Gtk.GestureClick` (button = 3) or `popup-menu` keyboard.
- Positioning: pointing-to coordinates, anchor.
- Context-sensitive enabling/disabling: per-instance actions with `install_action` on a parent widget.
- Passing a target value (e.g., the index of the row that was right-clicked).
- Long-press to open the same menu on touch.

## What you'll be able to do

- Attach a context menu to any widget, with actions that know what was clicked.
- Make context menus work for touch users too.

## Notes for the writer

- Keep this chapter small (~2 pages). It's a combinator of pieces from earlier chapters.
- Show a worked example: a list row with a right-click menu that operates on that specific row.
