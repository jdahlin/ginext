`packages/typelib` is the single in-repo build surface for test-only typelibs and
their generated stubs.

Current namespaces built here:

- `GIMarshallingTests-1.0`
- `Regress-1.0`
- `RegressUnix-1.0`
- `Utility-1.0`
- `GoiBench-1.0`

Planned additions belong here too, for example `GINextTest-1.0`.

## Provenance

Vendored from GNOME's `gobject-introspection-tests`:

- Upstream: `https://gitlab.gnome.org/GNOME/gobject-introspection-tests`
- Commit: `53e6bc978d5011f22d0a27cca49a94b19816ca7d`
- Files copied:
  - `annotation.[ch]`
  - `drawable.[ch]`
  - `foo.[ch]`
  - `gimarshallingtests.[ch]`
  - `gimarshallingtestsextra.[ch]`
  - `gitestmacros.h`
  - `regress.[ch]`
  - `regressextra.[ch]`
  - `regress-unix.[ch]`
  - `utility.[ch]`

The GoiBench benchmark typelib (originally a separate `goi-bench-typelib`) is
also built here:

- `bench.c`
- `bench.h`

## Notes

- `WarnLib` is intentionally not built here.
- Meson build outputs land under `build/.../packages/typelib/`.
- Native `.pyi` stubs for these namespaces are generated during the Meson build
  and installed under the same `ginext-stubs` top-level directory as the other
  shipped native stubs.
