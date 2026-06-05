# Meson layout for GNOME apps

> The de-facto build system. Meson handles asset compilation (GResource, GSettings schemas, desktop files, metainfo, icons), installation paths, and post-install hooks — most of which you don't want to write yourself.

## What this chapter covers

- A minimal `meson.build` for a Python GNOME app:
    - `project()` declaration.
    - `i18n`, `gnome`, `python` modules.
    - Configure-time substitution (`@APP_ID@`, `@VERSION@`).
- The `data/` directory:
    - `.desktop.in` → install with `i18n.merge_file` for translation.
    - `.metainfo.xml.in` → same.
    - GResource (`gnome.compile_resources`).
    - GSettings schema (`gnome.compile_schemas`).
    - Icons (scalable + symbolic).
- The `src/` directory:
    - Installing Python modules.
    - A console script generated from a `.in` template, with App ID baked in.
- Post-install hooks: updating the icon cache, mimeapps, schemas (`gnome.post_install`).
- Validation in CI: `desktop-file-validate`, `appstreamcli validate`, `glib-compile-schemas --strict`.
- Integrating gettext (`i18n.gettext`, `xgettext`, POTFILES.in).
- Combining meson (assets/install) with a Python build backend (uv/hatch) for source distribution.

## What you'll be able to do

- Author `meson.build` from scratch without consulting templates.
- Compile and install GResource, schemas, desktop, metainfo, and icons correctly.
- Validate everything in CI.

## Notes for the writer

- Show a complete, runnable `meson.build` as the centerpiece — annotated heavily.
- Note the version of meson and the `gnome` module being used.
