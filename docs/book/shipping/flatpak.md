# Flatpak and Flathub

> The default Linux distribution path for new apps. This chapter covers Flatpak the technology and Flathub the channel. (The GNOME-specific submission walkthrough is in [Publishing to Flathub](../gnome/flathub.md).)

## What this chapter covers

- Flatpak in one page: sandboxed apps, shared runtimes, OSTree-backed deltas.
- Runtimes: `org.gnome.Platform`, `org.kde.Platform`, `org.freedesktop.Platform` — pick one and stick with it.
- Anatomy of a manifest:
    - `app-id`, `runtime`, `runtime-version`, `sdk`, `command`.
    - `modules`: build steps for your app and dependencies.
    - `finish-args`: the sandbox permissions and portal access.
    - `cleanup`: stripping development cruft from the final bundle.
- Python-specific patterns:
    - Bundling pure-Python deps via `pip` or a generator (e.g., `req2flatpak`, `flatpak-pip-generator`).
    - Bundling C deps the manifest builds from source.
    - Locking sources to specific commits/hashes (required by Flathub).
- Local build/test loop:
    - `flatpak-builder --user --install build-dir manifest.json`.
    - `flatpak run <app-id>`.
    - Iterating quickly with `--state-dir` and `--ccache`.
- Distribution channels:
    - Flathub stable.
    - Flathub Beta.
    - GNOME Nightly (for in-development GNOME platform).
- Updates: how Flatpak deltas and OSTree-managed deployments work; what users see.
- End-of-life: how to mark an app EOL with redirect metadata.

## What you'll be able to do

- Author a Flathub-ready manifest and build it locally.
- Choose the right runtime and permissions.
- Maintain the manifest as the app evolves.

## Notes for the writer

- Complement, don't duplicate, [Publishing to Flathub](../gnome/flathub.md). That chapter is the submission process; this one is the tech.
