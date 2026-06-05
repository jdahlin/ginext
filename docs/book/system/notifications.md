# Notifications

> Sending notifications via `Gio.Notification` — which dispatches through the portal in sandboxed builds and falls back to direct DBus elsewhere. One API, many backends.

## What this chapter covers

- `Gio.Notification` essentials: title, body, icon, priority, category.
- Sending: `Gio.Application.send_notification(id, notification)`.
- Withdrawing: `withdraw_notification(id)` — and why IDs matter (replacement, deduplication).
- Action buttons: tying notification buttons to app actions (`add_button_with_target` / `set_default_action_and_target`).
- Persistence and the shell: which platforms persist after the app exits, which don't.
- Priorities (`LOW`, `NORMAL`, `HIGH`, `URGENT`) and what each does in GNOME/KDE.
- Sound and DnD: how the system handles these — don't try to override.
- Sandbox: the portal version takes over automatically; no code changes.
- Platform differences: GNOME Shell vs KDE notifications vs Windows toast vs macOS Notification Center.

## What you'll be able to do

- Send and update notifications correctly.
- Wire notification buttons to your app's actions.
- Reason about platform differences.

## Notes for the writer

- One real example: a "download complete" notification with an "Open file" action.
- Forward link to GNOME-specific "notifications done right" chapter in Part IV (best practices, persistence patterns).
