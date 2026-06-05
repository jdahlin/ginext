# DBus with GIO

> DBus is the message bus that the desktop session and most system daemons run on. GIO has full client and server bindings — no third-party library required.

## What this chapter covers

- DBus concepts in 90 seconds: bus types (session, system), well-known names, object paths, interfaces, methods, signals, properties.
- Connecting: `Gio.bus_get`, session vs system bus.
- Calling a method: `Gio.DBusConnection.call`, sync vs async, `GVariant` arguments and return values.
- `Gio.DBusProxy`: a typed-ish wrapper around a remote object.
- Subscribing to signals.
- Reading and watching properties (`org.freedesktop.DBus.Properties`).
- Introspection: discovering interfaces at runtime.
- Error handling: `Gio.DBusError` and how it maps to Python exceptions.
- Bus name ownership for single-instance apps.

## What you'll be able to do

- Call any DBus service from your app using only GIO.
- Subscribe to system-bus signals (network state, power, etc.).
- Read properties from a remote object and react to changes.

## Notes for the writer

- This is the foundation chapter for everything in Part III. Spend the time.
- Use `busctl` and `d-feet` / `D-Spy` as exploration tools — call them out.
- Cross-link forward to [Portals](portals.md) and the service-specific chapters.
