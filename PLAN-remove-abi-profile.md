# Plan: Remove ABIProfile / profile system

## Decision

If you use gi-compat, it applies to all objects globally — no per-profile isolation.
One shared root, one class per GType. Drop the profile system and the PYGOBJECT_COMPAT
feature flag.

The layering violation in `_overlays/GLib.py` (unconditional PYGOBJECT profile load for
GLibUnix) is a separate fix, not a blocker.

## What changes

### 1. Cache keys — remove the profile dimension

Four dicts keyed `(profile.name, ...)` simplify to just the type/name key:

| Dict | Before | After |
|------|--------|-------|
| `classbuild._classes_by_gtype` | `(profile.name, gtype_int)` | `gtype_int` |
| `record._record_classes_by_gtype` | `(profile.name, gtype_int)` | `gtype_int` |
| `record._record_classes_by_key` | `(profile.name, ns, ver, name)` | `(ns, ver, name)` |
| `enum._enum_classes_by_key` | `(profile.name, ns, ver, name)` | `(ns, ver, name)` |

### 2. NamespaceContext — drop the profile field

```python
# Before
@dataclass(frozen=True)
class NamespaceContext:
    name: str
    version: str
    profile: ABIProfile

# After
@dataclass(frozen=True)
class NamespaceContext:
    name: str
    version: str
```

### 3. Namespace module naming — always ginext.*

```python
# Before
def _namespace_module_name(name: str, profile: abi.ABIProfile) -> str:
    return profile.module_name(name)  # ginext.Gtk or gi.repository.Gtk

# After
def _namespace_module_name(name: str) -> str:
    return f"ginext.{name}"
```

### 4. abi.py — delete ABIProfile, NATIVE, PYGOBJECT

The entire `abi.py` file goes away (or becomes an empty shim if anything imports it).
`NamespaceContext` can move to `namespace.py`.

### 5. features.py — remove PYGOBJECT_COMPAT and its implied defaults

`PYGOBJECT_COMPAT` and the five flags it implies
(`NEW_PROPERTY_API`, `NEW_SIGNAL_API`, `GOBJECT_PROPERTY_CONSTRUCTOR`,
`OLD_SIGNAL_API`, `GERROR_BUILTIN_EXCEPTIONS`) are removed or collapsed to constants.

The remaining feature flags that are standalone (not profile-derived) survive as-is.

### 6. gimeta.profile — never set, never read

Remove all `gimeta.profile = ...` assignments and all `gimeta.profile` reads.
Remove the `profile` field from `GIMeta` stub in `private/__init__.pyi`.

### 7. gobject/subclass.py — user subclasses lose profile label

Remove the `if PYGOBJECT_COMPAT: gimeta.profile = PYGOBJECT` logic.

### 8. gobject/gtype.py — simplify pytype lookup

Remove the NATIVE→PYGOBJECT fallback in `GTypeMeta.pytype`.

### 9. overlay/install.py — drop profile parameter

`class_bases_overlay_for()` and `_resolve_dotted_type()` lose the `profile` parameter.

### 10. _overlays/GLib.py — fix layering violation (separate PR)

The unconditional `PYGOBJECT` profile load for `GLibUnix` deprecated values is a
layering violation. Fix separately after the profile system is removed.

## Files affected (~26 files, ~490 lines removed/simplified)

**Core:**
- `src/ginext/abi.py` — delete
- `src/ginext/__init__.py`
- `src/ginext/namespace.py`
- `src/ginext/classbuild.py`
- `src/ginext/enum.py`
- `src/ginext/record.py`
- `src/ginext/features.py`

**GObject system:**
- `src/ginext/gobject/subclass.py`
- `src/ginext/gobject/gtype.py`
- `src/ginext/gobject/gobjectclass.py`
- `src/ginext/gobject/metaclass.py`

**Overlays:**
- `src/ginext/overlay/install.py`
- `src/ginext/overlay/types.py`
- `src/ginext/_overlays/GObject.py`
- `src/ginext/aio.py`
- `src/ginext/signature.py`
- `src/ginext/private/__init__.pyi`

**Tests (~6 files):**
- `src/ginext/tests/classbuild/test_class_creation.py`
- `src/ginext/tests/conftest.py`
- `src/ginext/tests/glib/test_error.py`
- `src/ginext/tests/gobject/test_GObject_Type.py`
- `src/ginext/tests/namespace/test_overlay_bootstrap.py`
- `src/ginext/tests/signal/test_GObject_Object_gsignals.py`

## Approach

Do it incrementally in one branch:

1. Remove PYGOBJECT_COMPAT feature flag and its implied defaults — collapse all
   feature-flag checks to their non-compat defaults (typecheck + tests must pass)
2. Remove gimeta.profile reads/writes
3. Simplify cache keys (drop profile.name from tuples)
4. Drop profile parameter from overlay resolution
5. Remove NamespaceContext.profile, simplify namespace naming
6. Delete abi.py

The adoption dance (`_gobject_root_adopted`) and `init_gobject` are unaffected by this
change — that's a separate architectural step described in DESIGN-personalities.md.
