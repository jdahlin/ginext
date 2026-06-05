# Cross-platform overview

> A goi app built primarily for GNOME can almost always also run on Windows, macOS, and other Linux desktops. This chapter is the rule of thumb for what carries over and what doesn't.

## What this chapter covers

- The portability ladder:
    - **High portability**: GTK widgets, GIO, async, GSettings (with caveats), CSS, your app logic.
    - **Medium portability**: libadwaita patterns (work everywhere but look out-of-place on non-GNOME), portals (Linux only), GResource, gettext.
    - **Low portability**: distro-specific system services (NM, UPower, GOA), Mallard help, GNOME Shell integration.
- The "design GTK-first, opt into GNOME-second" strategy: keep platform-specific code at the edges, use feature detection at runtime.
- Runtime feature detection: checking for libadwaita, checking platform (`sys.platform`, `os.name`).
- The "what to drop on non-Linux" checklist:
    - Portals → native dialogs.
    - GSettings → keep (works everywhere) but be aware of the backend.
    - Notifications → native fallbacks.
    - DBus services → typically Linux-only.
- Cross-platform testing strategy: CI on three OSes from day one.

## What you'll be able to do

- Plan a project that targets multiple platforms without code duplication.
- Recognize the libraries and APIs that don't travel.

## Notes for the writer

- This is the navigational chapter for Part V; keep it short and link out heavily.
- One table summarizing the portability ladder is the most reused artifact.
