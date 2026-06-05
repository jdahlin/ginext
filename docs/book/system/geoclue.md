# GeoClue (location)

> The system location service. Use the **Location portal** by default; reach for GeoClue directly only outside sandboxed environments.

## What this chapter covers

- The portal path (recommended): request location access, receive updates, handle revocation.
- The direct path: GeoClue over DBus — `Manager`, `Client`, `Location` objects.
- Accuracy levels (`country`, `city`, `neighborhood`, `street`, `exact`) and what each means for the user prompt.
- Subscribing to location updates.
- Stopping cleanly to save battery.
- Privacy expectations: ask for the lowest accuracy that works.

## What you'll be able to do

- Get the user's location with their consent.
- Update efficiently and stop when no longer needed.

## Notes for the writer

- Tone matters: location is sensitive; the chapter should be respectful and emphasize least-privilege.
- One short example via the portal; mention the direct path briefly.
