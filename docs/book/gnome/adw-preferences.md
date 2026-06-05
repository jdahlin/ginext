# Preferences and About windows

> Stop hand-rolling these. libadwaita has canonical widgets that handle layout, search, and platform conventions for you.

## What this chapter covers

- `Adw.PreferencesDialog` / `Adw.PreferencesWindow`: the container.
- `Adw.PreferencesPage`: top-level tab/section with an icon and title.
- `Adw.PreferencesGroup`: a titled group of related rows.
- The row family:
    - `Adw.ActionRow` (label + subtitle + activatable).
    - `Adw.SwitchRow` (boolean setting).
    - `Adw.ComboRow` (enum/string-list selection).
    - `Adw.EntryRow` / `Adw.PasswordEntryRow`.
    - `Adw.SpinRow`.
    - `Adw.ExpanderRow`.
- Wiring rows to GSettings via `Gio.Settings.bind`.
- Built-in search across preferences pages.
- `Adw.AboutDialog` / `Adw.AboutWindow`:
    - Required fields (name, app-id, version, developer name, copyright, license).
    - Credits, acknowledgments, debug info, support URL.
    - "What's new" / release notes from AppStream.
- Adaptive sizing for both windows.

## What you'll be able to do

- Build a complete preferences UI in one screen of code.
- Show an About window that meets platform expectations.

## Notes for the writer

- This chapter is heavy on screenshots; show each row type.
- A worked "complete preferences UI bound to GSettings" example is gold here.
