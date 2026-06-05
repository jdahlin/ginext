# Notifications done right

> Notifications are easy to send. Notifications that *don't* annoy users are harder. This chapter is the GNOME-specific best practices on top of the [Notifications basics](../system/notifications.md).

## What this chapter covers

- The HIG rules: notifications are for *changes the user wasn't watching for*. Status of an action they just took belongs in a toast.
- Choosing transient vs persistent:
    - Transient (low priority): "download started." Auto-dismisses.
    - Persistent (normal/high): "build failed," "message received." Sits in the notification center until acknowledged.
- IDs and replacement: use a stable ID per logical notification so you replace rather than spam.
- Withdrawing: when the user has dealt with the thing inside your app, withdraw the notification.
- Action buttons: 1–2 max, with action verbs ("Reply," "Open file"), wired to `Gio.SimpleAction`s.
- Default action: clicking the body opens the relevant view in your app.
- Categories (`im.received`, `email.arrived`, `device.added`, …) — improve shell grouping and sound.
- DnD and "Quiet" mode: don't try to circumvent.
- Sounds: don't ship custom alert sounds for routine notifications.
- Testing: GNOME notification panel; `gdbus monitor` to see what's being sent.

## What you'll be able to do

- Send notifications users don't resent.
- Replace and withdraw correctly.
- Pick the right priority and category.

## Notes for the writer

- Use real examples of good and bad notifications (anonymized).
- The "you sent the notification, now don't keep showing it" pattern (withdraw when user opens the relevant view) is widely missed; emphasize.
