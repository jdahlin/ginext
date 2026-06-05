# The GNOME platform

> GNOME ships as a *platform*: a coordinated set of libraries with a release cadence, an ABI policy, and a Flatpak runtime. Knowing what's in the platform — and what isn't — saves time later.

## What this chapter covers

- The release cycle: two major releases a year (March/September), even/odd numbering, what changes between them.
- The Flatpak runtime: `org.gnome.Platform` and `org.gnome.Sdk`, what's bundled (GTK, libadwaita, GLib, Gio, Pango, Cairo, libsoup, WebKitGTK, GStreamer, more).
- ABI and API stability promises.
- Choosing a runtime version for your app and when to bump.
- "GNOME-platform" libraries you can rely on:
    - libadwaita, libsoup, libsecret, libportal, GTK4, Pango, Cairo, GStreamer (depending on runtime).
- "Adjacent" libraries (often present, not guaranteed): libsoup3, gst-plugins-good/bad, more.
- Distribution-shipped GNOME versions vs the Flathub runtime version (they diverge).
- What "GNOME Core" means and how a Core app differs from a Circle app (forward link).

## What you'll be able to do

- Pick a runtime version and justify it.
- Know which libraries you can use without bundling.
- Plan for the next platform bump before it lands.

## Notes for the writer

- This will date; keep a "as of GNOME 48" note and update.
- Show a `flatpak info --show-runtime org.gnome.Calendar` example so readers can see what real apps target.
