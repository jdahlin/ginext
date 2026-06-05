# logind (suspend, idle, lock)

> systemd-logind exposes the session and seat APIs that let your app inhibit suspend, observe lock/unlock, and react to logout.

## What this chapter covers

- Where logind lives: `org.freedesktop.login1` on the system bus.
- Inhibitor locks: `Inhibit("sleep:idle", who, why, mode)`. What "block" vs "delay" mean.
- The proper way: most apps should use the **Inhibit portal** instead — same effect, sandbox-friendly. Use logind directly only when the portal won't suffice.
- Reading session state: lock/unlock signals, idle hint.
- Reacting to suspend/resume (`PrepareForSleep` signal).
- Logout/shutdown notifications.

## What you'll be able to do

- Prevent the system from suspending during a long operation, and release the inhibit when done.
- Detect when the screen is locked or the user goes idle.
- React to suspend and resume cleanly.

## Notes for the writer

- Make the "portal first" rule explicit at the top.
- Show one inhibit example via the portal and one direct logind example, so readers can pick.
