# NetworkManager

> Network state, connectivity, and (when you really need it) configuring connections. For most apps, `Gio.NetworkMonitor` is enough; this chapter covers when it isn't.

## What this chapter covers

- The cheap path: `Gio.NetworkMonitor` — `network-available`, `connectivity`, change signals.
- When you need more: NM via DBus on the system bus.
- NM concepts: devices, active connections, settings, access points (Wi-Fi).
- Reading current state: SSID, signal strength, IPv4/IPv6 addresses, default route.
- Watching for state changes (online/offline, metered/unmetered, captive portal).
- Metered connections and respecting them.
- Listing saved connections; toggling Wi-Fi/airplane mode (requires policy/permissions).
- Sandbox considerations: NM is often unavailable inside strict sandboxes.

## What you'll be able to do

- React to going online/offline.
- Respect metered connections.
- Show network state when your app needs to.

## Notes for the writer

- Always recommend `NetworkMonitor` first; reach for NM only when needed.
- Note the equivalent on Windows/macOS (forward link to Part V) so cross-platform readers aren't stranded.
