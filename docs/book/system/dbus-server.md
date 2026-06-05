# Exposing your own DBus service

> When your app needs to be controlled from other apps, scripts, or the shell: own a bus name and export objects. Useful for single-instance apps, IPC, command-line tools that talk to a running GUI, and MPRIS implementations.

## What this chapter covers

- Owning a name: `Gio.bus_own_name`, name-acquired and name-lost callbacks, replacement policies.
- Exporting an object: defining an interface as XML, parsing with `Gio.DBusNodeInfo.new_for_xml`, and registering with `Gio.DBusConnection.register_object`.
- Handling method calls: the `method-call` callback, parameter unpacking, return values, errors.
- Emitting signals on your interface.
- Exposing properties (`org.freedesktop.DBus.Properties`).
- Patterns:
    - Single-instance apps via name ownership (versus `Gio.Application`'s built-in version).
    - A CLI command that talks to the running GUI.
    - Implementing MPRIS in your media app.
- Activation: `.service` files for on-demand startup.
- Testing your service with `busctl`, `gdbus`, and `D-Spy`.

## What you'll be able to do

- Own a name, export objects, accept calls, emit signals.
- Build a CLI that controls a running GUI.
- Implement MPRIS or a custom protocol for your app.

## Notes for the writer

- This is one of the most powerful underused chapters — many apps would benefit from a small DBus service.
- Show a complete tiny example: a `MyApp.Counter` service with `Increment` and an `OnChanged` signal.
- Cross-link to [MPRIS](mpris.md) as the headline use case.
