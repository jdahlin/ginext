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

### Our approach: a leaf `glib-gir` overlay (no cycle)

`tools/win/vcpkg-overlays/` holds local overlay ports (wired in via
`overlay-ports` in `vcpkg-configuration.json`).

An opt-in `introspection` *feature* on glib does **not** work: on a native build
host==target, so a `host: true` dep doesn't form a separate node and
`glib[introspection] → gobject-introspection → glib` collapses into a real cycle
(vcpkg "cycle detected"). Confirmed empirically.

Instead, **`glib-gir`** is a separate **leaf** port (nothing depends back on it,
so no cycle). It depends on stock `glib` + `gobject-introspection`, compiles the
matching glib sources a second time with `-Dintrospection=enabled`, and installs
**only** the typelibs the other two ports don't already own:
`GIRepository-3.0` (glib's self-introspection of its bundled `libgirepository-2.0`)
plus, on Windows, the `GLibWin32-2.0` / `GioWin32-2.0` platform typelibs. The
`GLib/GObject/Gio/GModule-2.0` typelibs continue to come from
`gobject-introspection`. This single overlay reproducibly replaces every typelib
that previously had to be hand-extracted from MSYS2.

The hard part was the Windows `g-ir-scanner` runtime (distutils, pkg-config,
`VCPKG_GI_DATADIR`, `gdump.c`); the portfile reuses gobject-introspection's own
`vcpkg-port-config.cmake` for the setuptools venv and wires the scanner env. See
the port-notes memory for the specifics.

**`gtk` / `gstreamer`** would use the same recipe (no cycle — they depend on
gobject-introspection normally) to produce their full typelib stacks, replacing
the old `gir-build.ps1` buildtree-poking and hand-built cp314 scanner. They are a
tracked follow-up (heavy source builds; opt-in features) — see status below.

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
- [x] **`glib-gir` overlay** — leaf port that compiles glib a second time with
      introspection on and ships only `GIRepository-3.0` + (Windows)
      `GLibWin32-2.0` / `GioWin32-2.0`. Validated on arm64-windows; reproducibly
      replaces the MSYS2-sourced typelibs.
- [x] GitHub Actions `windows-latest` (x64) + `windows-11-arm` (arm64) builders —
      pure-vcpkg dep install + clang-cl build + **core test suite**
      (`.github/workflows/ci-windows.yml`)
- [ ] `gtk` + `gstreamer` introspection overlays (follow-up): same scanner-env
      recipe as `glib-gir`, no cycle — but heavy/uncertain source builds on
      arm64 (vcpkg flags these ports unsupported there). Opt-in manifest features
      (`gtk`, `gstreamer`); their suites need these to run.

See the port notes memory for the LLP64/source fixes already committed.
