# Typing debt — `mypy --strict` rollout

Goal: **zero cast / Any / ignore**, full `--strict` everywhere.
No `Any`, no `cast`, no `# type: ignore` in consuming code — fix at the source.

---

## Current status (2026-06-01)

### mypy --strict errors (fresh cache, all packages)

| Package | Source errors | Test errors |
|---|---|---|
| `src/ginext` | **5** | **38** |
| `packages/ginext-gio` | **1** | **0** |
| `packages/ginext-gtk` | **0** | **0** |
| `packages/ginext-stubgen` | **0** | **0** |
| `scripts/` | **0** | **0** |
| `packages/ginext-gst` | **458** ⏳ | — |

**Note:** `packages/ginext-gtk` and `packages/ginext-gio` include overlays that use
`fn: Any` and `self: Any` pervasively (overlay mechanism — see §C below). These
show 0 errors because the `Any` cascades silence everything; the underlying
typing debt is documented in §C.

### Generated stubs (`ginext-stubs/*.pyi`)

**0 per-line `# type: ignore`** (was 8,990).
One **file-level directive** per stub: `# mypy: disable-error-code="override,type-arg,misc,valid-type"`.
This covers **44 irreducible errors** across all stubs if removed (see §D–F).

### `# type: ignore` in source code

| Location | Count | Notes |
|---|---|---|
| `src/ginext` source | ~18 | C-extension boundary, signature.py, gimeta accesses |
| `src/ginext` tests | ~133 | Intentional error paths, fixture subclassing |
| `packages/ginext-gio` | ~49 | GioUnix attribute accesses, arg-type at overlay boundary |
| `packages/ginext-gtk` | ~24 | overlay `fn: Any` boundary |

---

## A. `gimeta` on `Object` — 4 source errors

`src/ginext/_overlays/GObject.py` lines 249–274: `"type[Object]" has no attribute "gimeta"`.

The overlay accesses `cls.gimeta` where `cls: type[Object]`. In the stubs,
`gimeta: ClassVar[_GIMeta]` appears on each concrete class produced by the
metaclass, but the base `Object` type doesn't carry it in the stub (it's a
dynamically installed ClassVar). Fix: add `gimeta: ClassVar[_GIMeta]` to
`GObject.Object.body` in `native_overlays.toml`.

---

## B. `GioUnix` missing namespace — 1 source error

`packages/ginext-gio/src/ginext_gio/_overlays/GioUnix.py:20`:
`Module "ginext" has no attribute "GioUnix"`.

`GioUnix` is a Linux-only namespace; there is no stub for it. The stub for
`ginext` doesn't enumerate `GioUnix` because it's not in `_DEFAULT_NAMESPACES`.
Fix: add `GioUnix` to the stub generator's namespace list (with a platform guard),
or add `__getattr__ = ...` at the ginext stub level to silence the attr error.

---

## C. Overlay `fn: Any` / `self: Any` — ~200+ uses across ginext-gio, ginext-gtk

Every `@overlay.method` function has `fn: Any` (the injected C callable) and
`self: Any` for the GI-typed receiver. This is structurally necessary because:
- `fn` is injected at runtime and varies per overlay site
- `self` is the GI object; the stub types it as the concrete class, but the
  overlay file is in `ginext-gio`/`ginext-gtk` which don't know the exact type

Fix: define Protocol types for `fn` (e.g. `CallableAny = Callable[..., Any]`)
and use per-overlay type annotations for `self`. Significant but mechanical.

---

## D. `[override]` in stubs — 26 suppressed

Two patterns:
1. **`CellLayout.pack_end/pack_start`** — subclasses override with incompatible
   params. Fix: add `*args, **kwargs` to the base definition.
2. **`gi.repository.GObject.Object`** — compat stubs inherit from the compat
   GObject namespace; `connect`, `get_properties` etc. conflict. Fix: permissive
   overloads on compat GObject.Object.

---

## E. `[misc]` in stubs — 10 suppressed

1. **`class X(InitiallyUnowned)`** — `InitiallyUnowned` is `Any` (cross-namespace
   parent without `glib:type-name`). Fix: add `InitiallyUnowned` to TOML overlay.
2. **Diamond `activate_action`** — appears on both `Widget` and `ActionGroup`;
   mypy sees conflicting definitions. Fix: explicit override in the combining class.

---

## F. `[valid-type]` in stubs — 8 suppressed

`BuilderListItemFactory.bytes`, `BytesIcon.bytes` — GIR struct field named `bytes`
shadows the builtin type within the class body. Options:
- Add `bytes` back to `SHADOWED_BUILTINS` (renames field; breaks API)
- Use `builtins.bytes` for the type annotation
- Accept the suppression (current state)

---

## G. Test errors — 38 in src/ginext

| Category | Count | Root cause |
|---|---|---|
| `GLib2`, `GLib999`, `NoSuchNamespaceXYZ` etc. | 12 | Tests probe non-existent namespaces (intentional error-path tests). Irreducible without `type: ignore`. |
| `GLib.Error.new_literal`/`matches` takes `int` not `str` | 7 | GQuark is now correctly typed as `int`. Tests pass strings — either fix the tests or make the API accept `str | int`. |
| `Class cannot subclass GEnum/GFlags` (`[misc]`) | 6 | Fixture `GEnum`/`GFlags` typed as `Any`. Irreducible with fixture pattern. Fix: import directly. |
| `Module has no attribute "gobject"` | 3 | gi.repository compat layer access in feature tests. |
| `Module has no attribute "GIMarshallingTests"/"Regress"` | 4 | Test-only typelibs not in stubs. Irreducible without `type: ignore`. |
| `gimeta` on concrete test class | 1 | Same as §A — `gimeta` not on base `Object`. |
| `Unused "type: ignore"` | 3 | Stale ignores made redundant by improved stubs. Fix: remove them. |
| Misc one-offs | 2 | `PurePosixPath` arg, overlay bootstrap `SimpleNamespace` vs `Namespace`. |

---

## H. ginext-gst — 458 errors (pending)

Concurrent rewrite still in-flight. Same approach as src/ginext once settled.

---

## I. TOML-to-inline migrations

Entries in `native_overlays.toml` beyond `item_type`:
- `GObject.Object.body` C-slot methods → inline `.pyi` near C source
- `GLib.Error.body` → inline `.pyi`
- `GObject.Signal`/`Property` → inline `.pyi`

---

## J. `bytes`/`filter`/`set`/`range` in `_BUILTIN_EXCLUSIONS`

Excluded from `SHADOWED_BUILTINS` because GIR uses them as method/field names.
Must stay in sync with overlay additions. Documented in `stubgen/__init__.py`.

---

## K. cairo

`import cairo` (pycairo) is the correct pattern. `from ginext import cairo` is
forbidden. The stubs emit `import cairo` and `cairo.Context[cairo.Surface]` for
all GIR cairo references. `ginext-gtk` declares pycairo as a runtime dependency.

---

## Irreducible

- **File-level `disable-error-code`** in stubs — 44 genuine GI incompatibilities.
- **`signature.py` `[misc]`** — runtime generic alias construction.
- **Overlay `fn: Any`** — dynamically injected callable; reducible with Protocols.
- **Error-path tests** accessing non-existent namespaces — need `type: ignore`.
- **Test-only typelibs** (Regress, GIMarshallingTests) — not in stubs by design.
