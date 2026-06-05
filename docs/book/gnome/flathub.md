# Publishing to Flathub

> The canonical distribution channel for GNOME apps. This chapter is the end-to-end of "I have a working app" → "users can install it from Flathub."

## What this chapter covers

- Why Flathub is the default for GNOME apps: reach, automatic updates, sandbox, runtime parity.
- The Flatpak manifest in detail:
    - `app-id`, `runtime`, `runtime-version`, `sdk`, `command`.
    - `finish-args`: permissions (filesystem access, network, devices, portals).
    - `modules`: building your app and any non-runtime dependencies (note: most Python deps are not in the runtime — you bundle them).
    - Python module patterns for bundling deps (poetry/uv lockfile → flatpak module list).
- The Flathub submission process:
    - Forking `flathub/flathub`, opening a PR with your manifest.
    - The reviewer checklist (so you can self-check first).
    - Common rejection reasons: bad permissions, missing AppStream fields, network during build, vendor-bundling system libs.
- Building locally with `flatpak-builder` and testing.
- Beta channel: `flathub-beta` for pre-releases.
- After acceptance:
    - Maintaining your manifest in `flathub/<app-id>` repo.
    - The flatpak-external-data-checker for dependency updates.
    - Cutting a release: tag → manifest update → automatic build.
    - End-of-life and archiving.

## What you'll be able to do

- Author a Flathub-ready manifest for your app.
- Submit successfully on the first or second try.
- Maintain the manifest as your app evolves.

## Notes for the writer

- Provide a complete annotated manifest as the centerpiece.
- The reviewer checklist is the most valuable artifact — keep it current.
- Cross-link to [AppStream](appstream.md), [App ID](app-id.md), the [packaging](../shipping/flatpak.md) chapter in Part VIII.
