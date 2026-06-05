# Sway / wlroots / tiling WMs

> Tiling Wayland compositors (sway, hyprland, river, niri) are a small but vocal slice of the Linux desktop. GTK apps run; the rough edges are different from GNOME or KDE.

## What this chapter covers

- How GTK apps work under wlroots-based compositors: client-side decorations, no full-screen window servers.
- Window decoration etiquette: respecting `gtk-decoration-layout` settings, supporting compositor-side decorations where possible.
- Portals on wlroots:
    - `xdg-desktop-portal-wlr` for screenshot/screencast.
    - File chooser via `xdg-desktop-portal-gtk` (commonly).
    - What's incomplete and what isn't.
- Keyboard shortcuts: WMs intercept many key combos; design around it.
- Floating dialogs in a tiling WM: how to make modals usable.
- Themes: most tilers don't ship a default GTK theme; users configure their own. Don't fight it.
- Notifications: mako/dunst/fnott; standard `Gio.Notification` works.
- Testing: niri, sway, hyprland have different feature sets; check the ones you care about.

## What you'll be able to do

- Anticipate which features will feel weird on tiling compositors and design around them.
- Test on sway or niri to catch issues GNOME users won't see.

## Notes for the writer

- Audience is technical and opinionated; lead with respect.
- Pair with the cross-platform overview's "what won't carry" table.
