# Shell integration

> Beyond the app window: jump-list actions in the dock, single-instance handling, dynamic launcher (badges/progress), MPRIS for media. The features that make your app feel rooted in the desktop.

## What this chapter covers

- `.desktop` file `Actions=`: secondary actions exposed in the dock right-click menu (e.g., "New Window," "Compose Message"). How they map to app actions.
- Single-instance via `Gio.Application`: how second invocations reach the first, when to override `command-line` / `activate` / `open`.
- Dynamic launcher entries via the Unity launcher protocol (count badges, progress) — what works in GNOME, what doesn't.
- MPRIS for media apps (forward link to [MPRIS chapter](../system/mpris.md)).
- Status: GNOME has no system tray by design. Don't ship one; use notifications, background portal, or quick-settings extensions instead.
- Window state hints: skip-taskbar, urgency — when to use, when not to.

## What you'll be able to do

- Expose dock jump-list actions.
- Build a single-instance app that handles "open file from terminal" cleanly.
- Show progress and counts in the launcher where supported.

## Notes for the writer

- Be explicit about "no tray icons" — many cross-platform devs expect them and get frustrated.
- One example: a desktop file with Actions= and the corresponding app code.
