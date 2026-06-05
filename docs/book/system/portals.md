# Portals (xdg-desktop-portal)

> The **right default** for system integration in modern desktop apps. Portals work in Flatpak sandboxes, on every major Linux desktop, and they let users grant scoped permissions per app.

## What this chapter covers

- What a portal is: a sandboxed DBus interface that mediates access to OS features (files, screenshots, camera, etc.) with user consent.
- The portal architecture: backend (per desktop), frontend (`xdg-desktop-portal`), and the per-app proxy.
- Why portals matter even outside Flatpak: cross-desktop consistency, future-proofing.
- The portals you'll actually use:
    - `FileChooser` — open/save dialogs that look native and respect sandbox.
    - `Screenshot`, `ScreenCast`.
    - `Camera`.
    - `Notification` (the portal version of `Gio.Notification`).
    - `Inhibit` — prevent suspend/idle/logout.
    - `Background` — request to run in the background.
    - `Account` — request user info (name, avatar).
    - `Settings` — read desktop color-scheme and accent.
    - `OpenURI` — open URIs in the user's chosen app.
    - `Print`.
- Using portals from goi:
    - Directly via DBus.
    - Higher-level: `Gtk.FileDialog` and `Gio.Notification` use portals transparently when running sandboxed.
    - `libportal` (when present) for everything else.
- Permissions and the request flow.
- Testing portal interactions outside Flatpak.

## What you'll be able to do

- Use portals for file pickers, notifications, screenshots, and background activity.
- Build an app that works the same sandboxed or not.
- Know when *not* to use a portal (genuinely local, non-privileged operations).

## Notes for the writer

- Lead with the rule: **default to portals**, fall back to raw DBus / direct services only when needed.
- Show one tight example per portal.
- Pair with the [Flathub chapter](../gnome/flathub.md) since publishing is when portal correctness gets tested.
