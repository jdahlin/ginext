# Typelib versioning and .pyi stub generation

Design doc for two related features:

1. **Version-suffixed imports** — `from goi.repository import Gtk4` as a
   first-class, statically typecheckable alternative to
   `require_version("Gtk", "4.0")` + `from gi.repository import Gtk`.
2. **PEP 561 .pyi stubs** — a generator that emits per-namespace stubs from
   GIR XML, plus hand-written stubs for the `goi._goi` C extension and a
   stubgen pass over the Python overlays.

Target: Python 3.13+.

---

## Background — why both at once

The two features are coupled. Type checkers (mypy / pyright / ty) cannot
follow a runtime `require_version()` call to figure out which version of a
namespace to load. They see `from goi.repository import Gtk` as a single
name with a single stub, and have to pick one. The current PyGObject
ecosystem solves this by shipping per-major stub packages
(`pygobject-stubs` ships Gtk-4 by default; users install
`pygobject-stubs-Gtk3` to override). It's awkward and forces a packaging
dance to switch versions.

We can do better: make the import statement itself carry the version.
`from goi.repository import Gtk4` resolves to a single, unambiguous
`Gtk4.pyi` stub. No runtime call, no packaging dance.

The unsuffixed `from goi.repository import Gtk` keeps working for
PyGObject compatibility, but resolves through a system-detected default —
not a hardcoded table.

---

## Three categories of stubs

### Category 1 — `goi._goi` (the C extension)

The internal CPython extension module: heap types built with
`PyType_FromSpec`, module-level methods registered in `PyMethodDef`
tables, slots, etc. Surface is small and changes infrequently.

**Approach: hand-written `src/goi/_goi.pyi`.**

Auto-generating from runtime introspection is more complexity than the
small surface justifies. To get `inspect.signature(goi._goi.foo)` working
at runtime *in addition to* the static stub, retrofit
`__text_signature__` into the C docstrings using Argument Clinic format
(first line `funcname($module, arg, /)\n--\n\n…`). Already aligned with
how the `PyMethodDef` doc strings in `module_funcs.c` are shaped today.
Optional, low cost.

References:
- CPython issues [#107782](https://github.com/python/cpython/issues/107782),
  [#106310](https://github.com/python/cpython/issues/106310),
  [#68155](https://github.com/python/cpython/issues/68155) on
  `__text_signature__` for C-defined callables.
- numpy, lxml-stubs, pandas-stubs are all hand-written; this is the norm
  for non-trivial C extensions.

### Category 2 — Python overlays

`.py` files under `src/_goi/overlays/<NS>-<v>/` that customise GI
namespaces. Vanilla Python classes subclassing `goi.<NS>.<Class>`.

**Approach: run `mypy stubgen`, hand-fix, merge into the per-namespace
generated stub.**

Because `Variant.py` extends `GLib.Variant`, its stub output must merge
into `GLib.pyi` (category 3) rather than living in a separate file.

The TOML overlays (e.g. `Gdk-3.0.toml`, `GLib-2.0.toml`) are pure data
(aliases, kwarg defaults, shadowing) — they have no `.py` surface but
they *do* affect what category 3 emits (e.g.
`idle_add(function, *user_data, priority=...)` instead of the raw
`idle_add_full`). The generator reads them.

### Category 3 — GIR-based stubs

Everything reachable through `goi.repository.<NS>`: classes, methods,
constructors, properties, signals, vfuncs, enums, flags, callbacks,
varargs, GLib container types, out parameters, GError, etc.

**Approach: write our own generator from GIR XML.**

Decision: write fresh rather than fork
[pygobject-stubs](https://github.com/pygobject/pygobject-stubs), because:

- We need signal `connect()` overloads, `do_*` vfunc methods, and
  shadowing — all structurally missing from theirs.
- Our overlay TOML carries information that's invisible to their
  libgirepository walk.
- GIR XML beats the typelib for our purposes: it carries `shadows=`,
  `shadowed-by=`, `<doc>` elements, deprecation, transfer ownership,
  callback scope/closure/destroy indices, and `<glib:signal>` /
  `<virtual-method>` blocks. The compiled typelib drops or hides most of
  this.
- We already parse GIR XML in `tests/gir_coverage.py` — that code's the
  starting point.

#### Coverage targets

Things we want to handle beyond what pygobject-stubs covers:

- **Out / inout params** → tuple returns `tuple[ret, out1, out2]`.
  `raises=1` adds nothing to the tuple, just a docstring `Raises:
  GLib.Error`.
- **Container element types**: `GLib.List<Foo>` → `list[Foo]`;
  `GLib.HashTable<K,V>` → `dict[K,V]`; `GLib.Array<Foo>` → `list[Foo]`;
  `GLib.ByteArray` / `Bytes` → `bytes`.
- **Callbacks with scope** (`call` / `async` / `notified`) plus
  `closure` / `destroy` arg indices → drop `user_data` / `destroy` from
  the visible signature, expose `*user_data` (or `TypeVarTuple`).
- **Method shadowing**: emit only the shadowing method; the shadowed one
  becomes a comment. Requires GIR XML (libgirepository drops it).
- **Signals** → `@overload`s of `connect(self, signal_name:
  Literal["row-activated"], handler: Callable[[Self, ...], None],
  *user_data) -> int`. Inherit signals from parents.
- **Vfuncs** → `do_*` methods on classes (subclassers override them).
- **Properties with hyphens** → emit both `props.child_name` and a
  `Literal["child-name"]` overload for `connect("notify::child-name",
  …)`.
- **GType-fundamental aliases, disguised structs, unions** → empty
  `class`.
- **Varargs** in GI methods (rare; usually masked by overlays).

#### Prior art mined

- [pygobject-stubs](https://github.com/pygobject/pygobject-stubs) —
  closest fit. Reuse type-mapping tables and the `TypeVarTuple` trick for
  `*user_data` from `arguments.py`.
- [ts-for-gir](https://github.com/gjsify/ts-for-gir) — TypeScript `.d.ts`
  generator. Most polished signal-overload + callback design in this
  space; mine for shape.
- [gi-docgen](https://gitlab.gnome.org/GNOME/gi-docgen) — clean reference
  for normalising signal/property/vfunc info.
- [PGI](https://github.com/pygobject/pgi) `pgi/codegen/` — shows what's
  reachable from typelib alone (the floor we want to clear).

---

## Version-suffixed imports

### Runtime

`goi.repository.__getattr__` recognises a name as
`<Namespace><major_digits>` (e.g. `Gtk4`, `Gtk3`, `Adw1`, `Gst1`,
`GLib2`). It splits the digits off, validates the
`(namespace, version)` pair against the system, calls
`open_namespace(base, version)`, caches the result.

The unsuffixed `Gtk` keeps resolving as today: through prior
`require_version` if any, otherwise the system-detected default.

Suffix rule:
- Drop trailing `.0` from the GIR version (`Gtk-4.0` → `Gtk4`,
  `GLib-2.0` → `GLib2`, `Adw-1` → `Adw1`, `Gst-1.0` → `Gst1`,
  `GtkSource-5` → `GtkSource5`).
- Provide the full form (`Gtk_4_0`) as an alias for the rare case where
  minor versions diverge.

### Static (.pyi)

```
src/goi/repository/
  __init__.pyi
  Gtk4.pyi              (generated)
  Gtk3.pyi              (generated)
  Gtk.pyi               → Gtk4.pyi      (symlink, target = system default)
  GLib2.pyi             (generated)
  GLib.pyi              → GLib2.pyi     (symlink)
  Adw1.pyi              (generated)
  Adw.pyi               → Adw1.pyi      (symlink)
  …
```

**Why symlinks, not re-export stubs.** A re-export `Gtk.pyi` would have
to spell out `from .Gtk4 import Foo as Foo` for every public name to
satisfy pyright's strict-mode re-export rules. Symlinks sidestep this —
the stub *is* the other stub, no re-export semantics.

**Cross-platform.** mypy, pyright, ty all follow symlinks. POSIX +
Win10+ NTFS both support them. The remaining wrinkle is the wheel/pip
pipeline: ZIP has no native symlink entry, and pip's extractor will
likely materialise them as copies of the target. That's correctness-
preserving — we just lose the symlink-ness and pay a few extra KB.
Acceptable; verify in passing.

### Conflict semantics

- Suffixed import + prior `require_version` for a *different* version of
  the same namespace = error at the second import. Catches `import
  Gtk3` + `import Gtk4` in the same process early.
- Same-version suffixed import + `require_version` = no-op; both agree.

---

## Default version resolution

The existing `_DEFAULT_VERSIONS` table in
`src/goi/repository/__init__.py` is removed. Defaults are detected from
the system at runtime.

### Discovery mechanism

New C function:

```python
goi._goi._installed_versions() -> dict[str, list[str]]
```

Walks `g_irepository_get_search_path()`, scans for
`<Namespace>-<version>.typelib`, returns a dict mapping namespace name to
versions sorted descending by `(major, minor)`. Result is cached (one
walk per process unless explicitly invalidated).

Version comparison: split on `.`, pad to `(major, minor)`, compare as
ints. `"4.0"` > `"3.0"` > `"1.0"`. Adw's bare `"1"` becomes `(1, 0)`.

For the **build-time stub generator**, scan GIR XML at
`$XDG_DATA_DIRS/gir-1.0/*.gir` (typically `/usr/share/gir-1.0/`) using
the same logic. The generator emits one `.pyi` per
`(namespace, version)` it finds, and writes the unsuffixed symlink
pointing at the highest version per namespace.

### Resolver precedence (ordered list)

Design as an ordered list of sources from day one so future sources slot
in without touching call sites:

1. **`GOI_VERSIONS` env var** — `GOI_VERSIONS=Gtk:3.0,Gst:1.0`. Wins for
   ad-hoc overrides, CI matrix builds, etc.
2. **Programmatic `goi.set_default_versions({...})`** — primarily for
   tests.
3. **\[future, not today\]** `/etc/goi/defaults.toml` or
   `$XDG_CONFIG_HOME/goi/defaults.toml`. System / user configuration.
   Slots in between programmatic and auto-detected.
4. **Auto-detected highest installed version** — from
   `_installed_versions()`.

### `require_version` fate

Stays as a PyGObject-compatibility shim, but no longer load-bearing for
goi-native code:

- New code uses suffixed imports. `from goi.repository import Gtk4` is
  the new idiom.
- Existing PyGObject apps start with `gi.require_version("Gtk", "3.0")`
  + `from gi.repository import Gtk`. They keep working unchanged —
  `require_version` pins the unsuffixed name, equivalent to writing
  `from goi.repository import Gtk3 as Gtk`.
- Goi's own overlays, examples, and tests should stop calling
  `require_version`.
- Documentation labels it "compat shim — use suffixed imports instead."

Removing `require_version` entirely would silently break every existing
PyGObject app (they'd get the system-detected default instead of the
version they asked for). Don't do that.

---

## Packaging

**Inline** — `src/goi/py.typed` marker plus `.pyi` files next to
`_goi.so`. Not a separate `goi-stubs` package.

Rationale: stubs need to stay versioned with the C runtime and the
overlay TOML/.py files they describe. A separate PyPI release would lag
and create skew.

---

## Implementation plan

In order:

1. **`_installed_versions()` C function.** New entry in
   `goi._goi`, walks `g_irepository_get_search_path()`, returns the
   `dict[str, list[str]]`. Cached.
2. **Drop `_DEFAULT_VERSIONS`** from `src/goi/repository/__init__.py`.
   Wire the resolver-precedence list (env > programmatic > auto). Stub
   out the `(future)` config-file source as a TODO comment, no code yet.
3. **Suffixed-import resolution** in `repository/__init__.py`
   `__getattr__`: strip trailing digits, validate against
   `_installed_versions()`, call `open_namespace(base, version)`, cache.
   Plus the conflict-with-`require_version` check.
4. **Tests** covering: `from goi.repository import Gtk4` without prior
   `require_version`; `Gtk3` + `Gtk4` in same process errors; env
   override flips the unsuffixed default; `set_default_versions` flips
   it programmatically.
5. **Generator scaffold** under `tools/stubgen/`. First target:
   GLib-2.0 (smallest real namespace). Output to a temp dir, not into
   the source tree yet.
6. **Coverage levels** in order:
   1. Basic shape — classes, methods, constructors, properties, enums,
      flags, constants.
   2. Out / inout / GError / container element types.
   3. Callback scope + closure/destroy elision; TOML overlay rewrites
      applied here.
   4. Signal `connect()` overloads + property-hyphen literals.
   5. `do_*` vfunc methods.
   6. Method shadowing.
7. **`mypy stubgen` pass** over `src/_goi/overlays/<NS>-<v>/*.py`,
   merged into the per-namespace generated stubs.
8. **Hand-written `goi/_goi.pyi`** for category 1. Optionally retrofit
   `__text_signature__` into C docstrings in a second pass.
9. **Meson install** writes `.pyi` per namespace into the install tree
   alongside `_goi.so`, including the unsuffixed symlinks.
10. **`tox -e stubs`** target that regenerates stubs and runs
    mypy / pyright / ty over a small fixture project covering the
    headline patterns (out tuples, signal connect,
    `Gio.ListStore[Gio.File]`, `Variant("(si)", …)`).

---

## Open questions / not decided yet

- Whether to also alias version-suffixed names as `goi.repository.<NS>`
  attributes (so `goi.repository.Gtk4` works as well as `from
  goi.repository import Gtk4`). Probably yes — costs nothing extra given
  the `__getattr__` already handles it.
- Whether to ship the unsuffixed symlink at all, or always require the
  suffixed form for new code. Leaning toward keeping the symlink for the
  PyGObject-compat path; new code can ignore it.
- Whether `__text_signature__` retrofit happens in the same release as
  the stubs or later. Independent change; can ship whenever.
