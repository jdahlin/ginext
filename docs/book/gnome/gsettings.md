# GSettings the GNOME way

> Schemas authored for GNOME apps follow conventions that the Adw preferences widgets and `gsettings` CLI rely on. This chapter is the small pile of conventions on top of the [GSettings basics](../system/gsettings.md).

## What this chapter covers

- Schema ID matches App ID; path is the corresponding `/`-separated form.
- Key naming: lowercase, dash-separated, no shouting.
- Always supply `<summary>` and `<description>` for every key — translators and `gsettings list-keys` rely on them.
- Use enums and flags where possible — they survive renames and add validation.
- One schema per app for app settings; sub-schemas under the same prefix for distinct concerns (e.g., `org.gnome.MyApp.Editor`).
- Migration between versions: write to a new key, fall back to read-old-on-startup, drop after two releases.
- Wiring to `Adw.PreferencesPage`: `Gio.Settings.bind(key, widget, "active", DEFAULT)` patterns.
- Lockdown: deploying mandatory overrides via dconf for managed environments.

## What you'll be able to do

- Author schemas that match GNOME conventions.
- Hook settings into preferences UI declaratively.
- Migrate keys without breaking users.

## Notes for the writer

- This chapter is conventions, not API. Keep it short and link to [GSettings basics](../system/gsettings.md) for the actual mechanics.
