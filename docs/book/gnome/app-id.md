# App ID and naming conventions

> One reverse-DNS string identifies your app across the entire stack: desktop file, AppStream metainfo, GSettings schema path, DBus bus name, GResource path, icon name, Flatpak manifest. Get it right once.

## What this chapter covers

- The reverse-DNS rule: `tld.org.name` (`org.gnome.Calendar`, `io.github.username.AppName`).
- Where the App ID appears, with examples for each:
    - `.desktop` file name: `<app-id>.desktop`.
    - AppStream metainfo: `<app-id>.metainfo.xml` and `<id>` element.
    - GSettings schema: `<schema id="<app-id>" path="/tld/org/name/" />`.
    - GResource prefix: `/tld/org/name/`.
    - DBus bus name (from `Gio.Application`).
    - Icon name and icon files.
    - Flatpak manifest `id:` and `command:`.
- Naming dos and don'ts:
    - GitHub Pages users: `io.github.<user>.<App>`.
    - Hyphens vs dots; case sensitivity.
    - Dev vs nightly: appending `.Devel` or `.Nightly` and what changes (icon, GResource prefix, DBus name).
- Distinguishing release/development builds at runtime via App ID suffix.
- Worked example: a checklist of every place a freshly-renamed app needs updating.

## What you'll be able to do

- Choose an App ID and use it consistently.
- Ship parallel-installable nightly and stable builds with distinct IDs.

## Notes for the writer

- This is a *short* chapter but high-leverage. Make the checklist scannable.
- The "rename my app" checklist is the most useful artifact — keep it linked from the Builder, Flatpak, and Flathub chapters.
