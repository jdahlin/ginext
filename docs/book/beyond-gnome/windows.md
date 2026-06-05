# Windows

> GTK4 runs on Windows; goi runs on Windows. The result is real, but there are quirks. This chapter is the survival guide.

## What this chapter covers

- The two paths:
    - **MSYS2** with `mingw-w64-x86_64-gtk4` and `mingw-w64-x86_64-libadwaita` — the simplest dev path.
    - **gvsbuild** — Visual Studio builds (rarer; for shipping with the MSVC toolchain).
- Bundling GTK with your app for distribution (instead of asking users to install MSYS2).
- Native look and feel: how close does the default Adwaita theme get on Windows? When to consider a Windows-flavored theme.
- Window decorations, headerbars, and the title bar: GTK's headerbar vs Windows-native chrome.
- Fonts: Segoe UI, fallback chains, emoji rendering.
- File dialogs: GTK's vs Windows native (`Gtk.FileDialog` uses the native one when available).
- Where GNOME-isms break: portals (none on Windows), DBus (limited), `Gio.Notification` (uses Windows toast).
- Drag and drop with Windows Explorer.
- Common pitfalls: path separators, locale fallback, missing typelibs at runtime, GTK runtime version mismatches with MSYS2 updates.
- Packaging is in Part VIII; this chapter is *development*.

## What you'll be able to do

- Get goi running on Windows from MSYS2.
- Recognize and work around the Windows-specific gotchas.

## Notes for the writer

- Tone: GTK on Windows is good but not Apple-grade polished. Be honest.
- Cross-link to [Windows packaging](../shipping/windows.md).
