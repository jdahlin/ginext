# Search providers

> Expose your app's content in the GNOME Shell overview search. A DBus contract; not much code, big UX win for content-heavy apps.

## What this chapter covers

- The `org.gnome.Shell.SearchProvider2` interface.
- The contract:
    - `GetInitialResultSet` — match a query, return IDs.
    - `GetSubsearchResultSet` — narrow within a previous result set.
    - `GetResultMetas` — fetch display metadata (name, description, icon) for IDs.
    - `ActivateResult` — open the selected result.
    - `LaunchSearch` — fall through to your app's own search UI.
- Wiring:
    - The `.service` file for activation.
    - The `.ini` file in `/usr/share/gnome-shell/search-providers/`.
    - Bundling all of this in your app's data directory.
- Performance: results must come back fast; cache, index, or query Tracker.
- Sandbox: the Shell talks to your DBus name; the `.ini` and `.service` files install in fixed locations and are *not* sandboxed.
- Examples in the wild: Files, Photos, Calculator, third-party Circle apps.

## What you'll be able to do

- Make your app's content appear in the overview search.
- Open the right view when the user activates a result.

## Notes for the writer

- This chapter is high-leverage for media/notes/document apps.
- Show one tight implementation that wraps a small in-memory index; readers extend from there.
