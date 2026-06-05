# Tracker / Localsearch

> The GNOME index of local content (files, music, photos). If your app needs to find user content fast, query Tracker rather than walking the filesystem yourself.

## What this chapter covers

- What Tracker is in 2026: the rename to Localsearch, the separation of "miner" and "store" components, what's in the index.
- The SPARQL query interface: enough SPARQL to be useful.
- libtracker-sparql: connecting, querying, listening for updates.
- Common queries: "songs by artist," "photos taken in 2024," "documents matching a string."
- Adding your app's content to the index (Tracker resources, app-specific graphs).
- Sandbox considerations: portal access to the Tracker bus, what's reachable in Flatpak.
- When *not* to use Tracker (when your data is small or app-internal).

## What you'll be able to do

- Query the user's content index from your app.
- Reflect index updates in your UI live.

## Notes for the writer

- Limit SPARQL coverage to what's useful — readers don't need a full language tour.
- Show one example each for media, documents, and a custom graph.
- Verify current package names and DBus paths at writing time; this area has churned.
