# Bootstrapping ginext on Windows (x64 + arm64) via vcpkg

Goal of this series: reproducible Windows builders — `windows-latest` (x64) and
`windows-11-arm` (arm64) — that build ginext and run the test suite in GitHub
Actions. Everything below is triplet-agnostic; substitute `arm64-windows` /
`x64-windows` as needed.

## Why vcpkg, and the one hard problem

The native dependency graph (glib, gobject-introspection, cairo, gtk, gstreamer,
libffi, pkgconf) is declared in [`vcpkg.json`](../../vcpkg.json) and pinned to a
registry baseline in
[`vcpkg-configuration.json`](../../vcpkg-configuration.json). `vcpkg install`
(manifest mode) replaces every ad-hoc `vcpkg install <pkg>` command.

vcpkg's `gobject-introspection` port **already builds typelibs** for dynamic
triplets, so `GLib/GObject/Gio/GModule-2.0.typelib` come for free. The wrinkle:

* **`glib` ↔ `gobject-introspection` form a dependency cycle.** Since glib 2.80
  the `girepository-2.0` library moved *into* glib, so glib now needs
  `g-ir-scanner` (from gobject-introspection) which itself needs glib. vcpkg
  (master included) resolves this by shipping `glib` with
  `-Dintrospection=disabled`. The upstream-blessed fix is a two-pass
  `@bootstrap` build (FreeBSD/Yocto/MacPorts all do this).
* The only artifact we actually lose to that cycle is **`GIRepository-3.0.typelib`**
  (glib self-introspecting its bundled girepository). Historically this was
  hand-extracted from MSYS2.

### Our approach: overlay ports (tracked follow-up)

`tools/win/vcpkg-overlays/` holds local overlay ports (wired in via
`overlay-ports` in `vcpkg-configuration.json`):

1. **`glib`** — the cyclic one. glib 2.88 generates a *consistent*
   `GLib/GObject/Gio/GModule-2.0` + `GIRepository-3.0` typelib set from its own
   meson build (the `GIRepository-3.0` namespace matches glib's bundled
   `libgirepository-2.0`; this is a different, newer world than the standalone
   gobject-introspection 1.86 `GIRepository-2.0`/`libgirepository-1.0` typelibs).
   The robust way to get them is the upstream-blessed **two-pass / `@bootstrap`**
   build: glib-bootstrap (no GI) → gobject-introspection → glib (full, with
   typelibs). A post-install "scan only" hack was rejected because the scan needs
   glib's annotated *sources*, which the package doesn't install — at which point
   building glib with introspection is cleaner and correct.
2. **`gtk`** and **`gstreamer`** — flip introspection back **on**
   (`-Dintrospection=enabled`). These have *no* cycle: they depend on
   gobject-introspection normally, so the scanner is available and their full
   typelib stacks (Gtk/Gdk/Gsk/Pango/Graphene/GdkPixbuf, Gst*) are produced by
   vcpkg directly — replacing the old `gir-build.ps1` buildtree-poking and the
   hand-built cp314 scanner.

Result, once landed: **all typelibs become vcpkg build artifacts** under
`installed/<triplet>/lib/girepository-1.0/`. No MSYS2 extraction, no manual
scanner, no `C:\dev\gitl`. These overlays need real build iteration and are
validated through the Windows CI in this series — see status below.

## Toolchain (host-native per triplet)

* MSVC Build Tools 2022 (CRT + Windows SDK; ARM64 workload on arm64).
* **clang-cl + lld-link** (LLVM) — ginext is GNU-C (`__attribute__((cleanup))`,
  `g_autoptr`); MSVC `cl.exe` cannot compile it. clang-cl gives GNU extensions
  with the MSVC ABI. Both triplets.
* Native CPython 3.14 (the build/runtime Python for ginext).
* A build venv with meson, ninja, meson-python, pytest(+xdist,timeout), pycairo,
  setuptools, tzdata.

## End-to-end flow

```
vcpkg install --triplet <triplet>      # manifest mode; overlays produce all typelibs
. tools/win/build-env.ps1              # vcvars + clang-cl + pkgconf + GI_TYPELIB_PATH (-> vcpkg install tree)
tools/win/build.ps1                    # meson setup (native file) + compile
tools/win/run_tests.py ...             # suite
```

All paths (vcpkg root, LLVM, Python, triplet) are parameterized — see
`build-env.ps1`. CI passes them as inputs so the same scripts drive x64 and arm64.

## Status / open items

- [x] `vcpkg.json` + `vcpkg-configuration.json` (manifest + pinned baseline)
- [x] de-hardcode `build-env.ps1` / `build.ps1` / `setup.ps1` (triplet-agnostic)
- [x] GitHub Actions `windows-latest` (x64) + `windows-11-arm` (arm64) builders —
      pure-vcpkg dep install + clang-cl build of ginext (`.github/workflows/ci-windows.yml`)
- [ ] overlay `glib` two-pass → `GIRepository-3.0` + consistent core typelibs
- [ ] overlay `gtk` + `gstreamer` introspection
- [ ] enable the CI test step once the typelib overlays land

See the port notes memory for the LLP64/source fixes already committed.
