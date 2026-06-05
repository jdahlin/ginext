# vcpkg overlay ports (Windows bootstrap)

Wired in via `overlay-ports` in the repo-root `vcpkg-configuration.json`.

These overlays exist to re-enable **GObject-Introspection typelib generation**,
which upstream vcpkg disables. See [`../BOOTSTRAP.md`](../BOOTSTRAP.md) for the
full design and the glib ↔ gobject-introspection cycle this works around.

## Planned ports (tracked follow-up — not yet landed)

- **`glib`** — two-pass / `@bootstrap` build that enables `-Dintrospection=enabled`
  so glib emits a consistent `GLib/GObject/Gio/GModule-2.0` + `GIRepository-3.0`
  typelib set (the version that matches glib's bundled `girepository-2.0`).
- **`gtk`**, **`gstreamer`** — flip introspection back on (no cycle; they depend
  on gobject-introspection normally) to produce their full typelib stacks.

Until these land, typelibs are supplied out-of-band (see the port notes); the CI
builders in this PR validate that the pure-vcpkg dependency install + clang-cl
build of ginext succeeds on `x64-windows` and `arm64-windows`.
