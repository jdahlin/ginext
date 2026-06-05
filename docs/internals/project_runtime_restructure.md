---
name: runtime restructure plan
description: Agreed target file structure for src/runtime/ after collapsing types/ and renaming
type: project
---

Agreed target layout for `src/runtime/` (all filenames use hyphens, not underscores).
`types/` directory is eliminated — everything moves into `runtime/`.
`augment.c/h` will be deleted separately.

## Target files

### GObject layer
- `gobject-base.c/h` — GObjectBase HPy type + wrap/unwrap + object-info + interface-info marshal
- `class-registry.c/h` — Python type → GType/GIObjectInfo registry (split from gobject_base)
- `object-class.c/h` — build Python class from GIObjectInfo (was object_class_builder)
- `lazy.c/h` — LazyNamespace only (MethodDescriptor moves out)
- `enum.c/h` — enum-info + flags-info marshal + Python enum/flags type builder

### Callable/Invoke pipeline
- `callable.c/h` — MethodDescriptor type + descriptor builder + shape diagnostics
- `invoke.c/h` — main FFI invocation loop (was method.c)
- `invoke-plan.c/h` — pre-scan for implicit arg slots (was invoke_plan)
- `invoke-return.c/h` — return + OUT param assembly (was invoke_return)
- `in-cleanup.c/h` — IN arg cleanup tracking (was in_cleanup)

### Marshaling
- `marshal.c/h` — GIArgument ↔ HPy dispatch (was giargument)
- `c-array.c/h` — C array (GI_ARRAY_TYPE_C) IN + OUT (was c_array_in; py_item_to_gvariant moves to variant)
- `array.c/h` — GArray/GPtrArray/GByteArray
- `glists.c/h` — GList + GSList (slist.c was already a stub delegating to glist.c)
- `ghashtable.c/h` — GHashTable (was ghash)
- `gvalue.c/h` — GValue
- `variant.c/h` — GVariant + pygir_py_item_to_gvariant (moved from c_array_in)
- `scalar.c/h` — bool, int*/uint* 8-64, float, double, unichar, void, gtype + primitive storage helpers
- `string.c/h` — utf8 + filename

### Infrastructure
- `closure.c/h` — libffi callback closures (was types/callback.c)
- `effective.c/h` — GIR namespace + override resolution
- `overrides.c/h` — ZIP-based override file loading
- `type-info.c/h` — GITypeInfo/GIBaseInfo utilities (was type_info)

### Unchanged
- `jit/` — unchanged

## Key decisions
- `pygir_` prefix for all public API (headers); already consistent
- Internal static helpers use domain prefix: `gi_`, `gvalue_`, `jit_` etc — not `pygir_`
- `h_*` JIT helpers in core.c: low priority rename (static, file-private)
- More naming renames deferred ("not yet" — will tackle after restructure)

**Why:** avoid large files (target ~300-800 lines each); types/ had too many tiny files and fuzzy boundary with runtime/; invoke/callable/method concepts now clearly separated.
