# Snap

> Canonical's universal package format. Strict by default, classic for opt-out. Smaller GTK ecosystem than Flatpak but real reach on Ubuntu.

## What this chapter covers

- Snap concepts: snaps, channels (stable/candidate/beta/edge), tracks, confinement (strict/classic/devmode).
- `snapcraft.yaml` anatomy:
    - `name`, `base` (`core24` etc.), `confinement`, `grade`.
    - `apps`: command, plugs, slots, daemon mode.
    - `parts`: build steps.
- The `gnome` extension: pulls in GTK4 + libadwaita from a content snap, saves you bundling.
- Permissions (plugs): home, network, audio, removable-media, etc.
- Building locally:
    - `snapcraft pack` and the build VM.
    - Installing locally with `snap install --dangerous *.snap`.
- The Snap Store:
    - Account, namespace, registering the name.
    - Uploading and promoting through channels.
    - Auto-updates (you can't opt out as a user — design accordingly).
- Strict vs classic for GTK apps; how confinement affects portals.
- Performance/startup considerations (mount-time, AppArmor profiles).

## What you'll be able to do

- Build a snap of your goi app.
- Publish to the Snap Store with reasonable confinement.

## Notes for the writer

- Acknowledge that snap is contentious in some communities; this chapter is neutral and practical.
- Cross-link to the GNOME extension for snap (which mirrors Flatpak's runtime concept).
