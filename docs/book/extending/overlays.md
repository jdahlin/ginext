# Pygir overlays

> When a C library exists and its introspection is imperfect — or you want a more Pythonic surface — write an overlay. This is goi's documented escape hatch.

## What this chapter covers

- What an overlay is: a Python module in `goi/overlays/<Namespace>/...` that augments or replaces the auto-generated binding for a namespace.
- When to write an overlay:
    - Upstream forgot a `(nullable)` annotation; you don't want to wait for a release.
    - The C API takes a verbose argument list and a Pythonic shortcut would help (`Bytes(data)` instead of `Bytes.new(data)`).
    - A constant or method is misnamed for Python conventions.
    - You want to expose a Pythonic property or method that wraps a sequence of C calls.
- When *not* to write an overlay: when the right fix is upstream (file the bug).
- Reading existing overlays in `src/overlays/` as the reference.
- Patterns you'll see:
    - Imported names (`__imported__.py`).
    - Constructor shortcuts (`__new__`).
    - Method patching.
    - Type aliasing.
- Testing your overlay: round-tripping via `tests/`.
- Versioning: overlays vs upstream — when to retire an overlay after upstream fixes the API.

## What you'll be able to do

- Add an overlay to fix a binding issue without waiting for upstream.
- Recognize when an overlay is the wrong tool and a bug report is the right one.

## Notes for the writer

- Pull examples from the actual overlays in this repo — `GLib-2.0/Bytes`, `GObject-2.0/__imported__`, etc.
- The PyGObject migration audience cares about this because it's where goi is most different.
