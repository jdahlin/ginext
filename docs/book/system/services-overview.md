# System services overview

> A map of the system-level DBus services your app might want to talk to, and a decision tree for picking the right approach (portal? direct DBus? high-level binding?).

## What this chapter covers

- A one-page table:
    - **Need** → **Best option** → **Fallback** → **Why**.
    - Examples:
        - "Show a notification" → `Gio.Notification` (portal-aware) → custom DBus only if you need exotic features.
        - "Get battery state" → UPower → direct sysfs (don't).
        - "Open a file picker" → portal `FileChooser` (via `Gtk.FileDialog`) → none.
        - "Persistent location" → portal `Location` / GeoClue → none.
        - "Network connectivity status" → `Gio.NetworkMonitor` (already handles NM) → NM directly.
- The decision tree: portal first, high-level GIO/GLib API second, direct DBus to the service third.
- Sandbox implications: which services are reachable from Flatpak by default, which need explicit permissions, which require a portal mediator.

## What you'll be able to do

- Pick the right integration mechanism for a given need without spelunking through five docs sites.

## Notes for the writer

- This is a *navigational* chapter. Keep it tight; the depth lives in the per-service chapters.
- Maintain the table as the canonical "where do I look" reference.
