# Tracker for content apps

> The GNOME-specific patterns for integrating Tracker/Localsearch into a content app. Builds on the [Tracker basics](../system/tracker.md).

## What this chapter covers

- Apps that benefit: music, photos, videos, documents, notes.
- Querying patterns:
    - "All FLAC files added in the last week."
    - "Photos with location near Paris."
    - "Documents containing X."
- Listening for index changes and updating your UI live.
- Adding your app's content to the index (custom ontologies, app-specific resources) — when this is worth doing.
- Performance: incremental queries, paged results, async iteration.
- Sandbox: declaring Tracker access in your Flatpak manifest, the user-content permissions.
- Fallback behavior when Tracker is unavailable or empty.

## What you'll be able to do

- Build a content app that uses the system index instead of crawling.
- Expose your own data through Tracker for other apps to find.

## Notes for the writer

- Keep this focused on GNOME-app integration patterns; the SPARQL primer lives in Part III.
- One example app: a "recent photos" sidebar driven by Tracker.
