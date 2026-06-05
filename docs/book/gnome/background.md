# Background apps and autostart

> Sometimes your app needs to keep running with no visible window — sync clients, chat apps, media servers. GNOME has a specific contract for this.

## What this chapter covers

- The Background portal: requesting permission to run in the background, declaring why.
- Conventions: the user must be able to see and revoke background-running apps from Settings.
- `Gtk.Application.hold` / `release` to keep the app alive while there are no windows.
- The `XDG_AUTOSTART` mechanism for "start when the user logs in" — `.desktop` files with `X-GNOME-Autostart-enabled=true`.
- The hidden-window pattern for resident apps; how the app exposes a quick way to bring up its UI.
- Status notifier (KDE-style tray) and why GNOME doesn't show one — alternatives for users on other DEs (Part V cross-link).
- DBus activation: starting on demand when something messages your bus name.
- Power and battery considerations: don't burn cycles when idle; wake on real events only.

## What you'll be able to do

- Run a daemon-like app idiomatically on GNOME.
- Autostart your app where appropriate, without surprising users.

## Notes for the writer

- Be cautious about "always run" — GNOME's design discourages it.
- One example: a sync client that runs in the background and shows a window on demand.
