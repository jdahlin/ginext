# Packaging foundations

> Shared across every Linux target and most non-Linux ones: the metadata files, icons, and assets that every package format consumes.

## What this chapter covers

- The `.desktop` file:
    - Required keys (`Type`, `Name`, `Exec`, `Icon`, `Categories`).
    - `MimeType` for file-association apps.
    - `Actions=` for jump-list entries.
    - `StartupWMClass` for window matching.
    - Validation with `desktop-file-validate`.
- AppStream metainfo (cross-link to the [detailed chapter](../gnome/appstream.md)).
- Icon sets:
    - Scalable SVG at the canonical sizes.
    - Symbolic icons.
    - Install paths under `data/icons/hicolor/`.
- GResource bundling.
- GSettings schema installation and runtime resolution.
- The post-install rituals: `update-desktop-database`, `gtk-update-icon-cache`, `glib-compile-schemas`. What runs them in each package format.
- Versioning conventions: semver vs date-versioning; sortable strings.
- Release notes living in AppStream and referenced from your changelog.
- A "ready to ship" checklist that gates everything else in Part VIII.

## What you'll be able to do

- Author the files every package format requires before you write a single packaging recipe.
- Validate them in CI so packaging errors fail fast.

## Notes for the writer

- The pre-ship checklist is the most-reused artifact.
- Tie back to the GNOME-specific App ID and AppStream chapters; here it's the cross-platform view.
