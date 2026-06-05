# vcpkg overlay ports (Windows bootstrap)

Wired in via `overlay-ports` in the repo-root `vcpkg-configuration.json`.

These overlays re-enable **GObject-Introspection typelib generation**, which
upstream vcpkg disables. See [`../BOOTSTRAP.md`](../BOOTSTRAP.md) for the full
design and the glib ↔ gobject-introspection cycle they work around.

## Ports

- **`glib-gir`** *(landed, validated on arm64-windows)* — a leaf port that
  compiles glib a second time with introspection enabled and installs only
  `GIRepository-3.0` plus, on Windows, the `GLibWin32-2.0` / `GioWin32-2.0`
  platform typelibs (the artifacts that previously had to be copied from MSYS2).
  Being a leaf, it avoids the glib ↔ gobject-introspection cycle that blocks an
  introspection feature on glib itself, and it ships only typelibs so it does not
  conflict with the `glib` / `gobject-introspection` ports.

## Planned (tracked follow-up)

- **`gtk`**, **`gstreamer`** introspection overlays — same scanner-env recipe as
  `glib-gir`, no cycle. Deferred: heavy/uncertain source builds on arm64. Their
  test suites (opt-in `gtk` / `gstreamer` manifest features) need them.
