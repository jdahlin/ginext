# macOS

> GTK4 runs on macOS — natively on Quartz, no X server. goi works. Polish is a journey.

## What this chapter covers

- Installing the GTK runtime: Homebrew (`gtk4`, `libadwaita`, `gobject-introspection`, `py3cairo`).
- Running your app: `python my_app.py` works; common path issues with `DYLD_LIBRARY_PATH`, `GI_TYPELIB_PATH`.
- Native macOS feel:
    - Menu bar: how to put your `Gio.Menu` on the macOS menu bar (currently limited).
    - The traffic-light buttons and how GTK draws windows on macOS.
    - macOS keyboard shortcuts (`Cmd` vs `Ctrl`).
- Fonts: SF Pro fallback, emoji color rendering.
- File dialogs: GTK uses native NSOpenPanel where supported.
- Where GNOME-isms break:
    - libadwaita's adaptive UI works visually; some interactions (back gestures) feel non-native.
    - Portals: none on macOS.
    - DBus: not available; use platform-native alternatives.
- Trackpad gestures and pinch-to-zoom.
- HiDPI on Retina: usually fine; check pixmap sources.
- Common pitfalls: signing/notarization show up early (the OS refuses to run unsigned binaries); Homebrew GTK upgrades breaking your dev environment.

## What you'll be able to do

- Run a goi app on macOS for development.
- Know the limits and design around them.

## Notes for the writer

- macOS GTK is the least polished of the three big targets. Don't oversell.
- Packaging (`.app` + notarization) is in Part VIII; this chapter is dev.
