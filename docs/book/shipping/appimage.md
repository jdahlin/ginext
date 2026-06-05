# AppImage

> A single-file binary that runs almost anywhere. Bundles everything; no installer; no central store. Good for niche tools and side-channel distribution; less polished than Flatpak/Snap for GUI apps.

## What this chapter covers

- The AppImage model: SquashFS-packed AppDir mounted at runtime, runs as a regular binary.
- `AppDir/` layout: `AppRun`, `usr/`, `data/`, the embedded `.desktop` and icons.
- `linuxdeploy` + `linuxdeploy-plugin-gtk`: the standard tooling for GTK apps.
- Bundling goi + Python:
    - Python interpreter inside the AppImage.
    - Site-packages with your deps and goi.
    - GTK and dependent shared libs.
    - The typelib and GResource data.
- Tradeoffs vs Flatpak:
    - No sandbox.
    - No automatic updates (zsync-based optional updater).
    - Larger file size; no shared runtimes.
    - Works on near-any glibc-recent Linux.
- Updates with `AppImageUpdate` (optional).
- Integration: desktop integration scripts (e.g., `appimaged`); how users install.
- Common failure modes: missing typelibs, missing modules, GLib schema not found at runtime.

## What you'll be able to do

- Produce a working AppImage of your goi app.
- Decide whether AppImage is worth shipping alongside Flatpak.

## Notes for the writer

- Be candid: AppImage is a fine third channel, rarely a primary one for GUI apps.
- One worked recipe: linuxdeploy invocation that produces a runnable AppImage.
