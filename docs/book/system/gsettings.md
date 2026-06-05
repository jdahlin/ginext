# GSettings

> The configuration store for GTK apps: typed keys, schemas, change notifications, atomic transactions. Far better than rolling your own JSON file.

## What this chapter covers

- The model: schemas (XML, compiled to a binary blob) + a backend (dconf, on Linux).
- Authoring a schema:
    - `<schema id="org.example.MyApp" path="/org/example/myapp/">`.
    - Key types: booleans, strings, ints, doubles, enums, flags, arrays, dicts, custom `GVariant` types.
    - Defaults, ranges, choices, summaries, descriptions.
- Compiling and installing:
    - `glib-compile-schemas` at install time.
    - Meson integration.
    - For dev: setting `GSETTINGS_SCHEMA_DIR` so you can run uninstalled.
- Reading and writing from Python:
    - `Gio.Settings`, `get_*` / `set_*`, atomic `delay()` / `apply()`.
    - Binding settings to widget properties (`bind`, `bind_with_mapping`).
    - Watching for changes (`changed::key` signal).
- Migration: changing schemas across versions without losing user data.
- Sandbox: schemas in Flatpak (installed into the runtime, not host).
- Lockdown and policy (`mandatory` overrides).

## What you'll be able to do

- Design a settings schema for your app.
- Bind settings directly to widgets so prefs UIs are mostly declarative.
- Migrate keys across versions safely.

## Notes for the writer

- This chapter lives in Part III because every app needs it; the GNOME-specific Preferences UI patterns come in Part IV.
- Show the full lifecycle: define schema → compile in meson → bind to a switch.
