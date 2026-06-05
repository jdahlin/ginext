# KDE Plasma

> Many of your users will be on KDE. GTK apps run fine; the goal is making them feel like reasonable citizens rather than visibly out-of-place.

## What this chapter covers

- The Breeze GTK theme: what it does, when it doesn't ship by default, how users install it.
- File dialogs: Plasma's portal backend means your `Gtk.FileDialog` opens a Plasma-native chooser (when configured).
- Notifications: Plasma's notification daemon receives them transparently.
- Tray icons: Plasma *does* have a working tray; the StatusNotifier protocol. If you decided not to ship a tray for GNOME, consider that some Plasma users expect one and decide how to handle it.
- Color scheme detection: how to follow the KDE color scheme (light/dark) the same way you follow GNOME's.
- Plasma quick-settings / activities — not something most apps need to integrate with.
- Tilix-style headerbar concerns: KDE users sometimes prefer client-side decorations off; GTK's headerbar respects this less gracefully.
- Application menus: KDE's global menu integration with GTK apps.

## What you'll be able to do

- Make your app look reasonable on Plasma without changing code.
- Decide how to handle tray icons / global menu conventions.

## Notes for the writer

- Keep KDE Plasma's strong points front and center; many readers' users are here.
- Acknowledge GTK on KDE will never be perfectly native, and that's OK.
