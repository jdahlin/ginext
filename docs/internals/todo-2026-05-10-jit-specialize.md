# JIT specialization — kill generic kind-dispatch on the hot path

## Problem

The x86_64 trampolines we emit today contain **two kinds of generic dispatch**:

1. **Indirect calls through the helper table.** For each arg and the return,
   we look up a `PygirHelper*ToHpy` / `PygirHelperHpyTo*` slot via
   `pygir_jit_marshal_helper_for(kind)` / `pygir_jit_unmarshal_helper_for(kind)`
   and emit `call [slot]`. The helper is a tiny C wrapper around
   `PyLong_FromLong`, `PyFloat_AsDouble`, etc. — one indirect call per arg
   per call.
2. **Runtime kind switches inside helpers.** `h_check_arg_type` (helpers.c:276)
   takes `PygirTypeKind` and switches on it for every arg of every call.

For a 3-arg INT32→INT32 call the trampoline issues ~7 indirect calls for
work that is, per kind, three or four x86 instructions inline.

The plan-time generic functions (`gi_to_goi_type`, `can_direct_scalar_out`)
run once per descriptor build and are not hot — they stay generic.

## The six generic functions

Hot (specialize / inline at emit time):

| # | Function | Location | Notes |
|---|---|---|---|
| 1 | `pygir_jit_marshal_helper_for` | `src/jit/helpers.c:525` | Return marshal slot lookup |
| 2 | `pygir_jit_unmarshal_helper_for` | `src/jit/helpers.c:500` | Per-arg unmarshal slot lookup |
| 3 | `h_check_arg_type` | `src/jit/helpers.c:276` | Per-arg type check, switches on kind |
| 4 | `x86_64_sysv_emit` (catch-all path) | `src/jit/arch/x86_64_sysv.c:875` | Single emitter for all shapes; works via the table above |

Cold (leave generic — runs at compile time, not per call):

| # | Function | Location | Notes |
|---|---|---|---|
| 5 | `gi_to_goi_type` | `src/invoke/jit/plan.c:37` | Once per descriptor |
| 6 | `can_direct_scalar_out` | `src/invoke/jit/plan.c:111` | Once per descriptor |

## Goal

Replace the helper-table indirection with **per-kind emit functions** that
write the conversion sequence directly into the trampoline. Each `PygirTypeKind`
gets one `emit_unmarshal_<kind>` and one `emit_marshal_<kind>` per arch.

For INT32 unmarshal, instead of:

```
mov   rdi, [rbp-CTX]            ; ctx
mov   rsi, [rbp+ARG]            ; PyObject*
call  [helper_table + slot]     ; → h_py_to_int32 → pygir_pyobj_to_long
```

we want either:

- **Inlined fast path + slow-path tail call** when the value is `PyLong`:
  ```
  mov   rsi, [rbp+ARG]
  cmp   qword [rsi+OB_TYPE_OFF], &PyLong_Type
  jne   .slow
  ; inline PyLong_AsLong fast path (or call _PyLong_AsInt32 directly)
  ```
- **Direct call to the CPython API** when no Python-side fast path applies:
  ```
  mov   rdi, [rbp+ARG]
  call  [PyLong_AsLong_slot]    ; one fewer hop than via h_py_to_int32
  ```

Same shape for marshal: `PyLong_FromLong(v)` directly instead of via
`h_int32_to_py(ctx, v)`.

## Phasing (reprioritized 2026-05-10 after drawing-app trace analysis)

A real GUI invoke trace from the drawing app showed: ~12× `set_enabled(action, bool)`,
~6× `lookup_action(win, str) → GObject`, ~5× `set_label/set_tooltip(widget, str_or_None)`,
~4× `get_current_page/get_width()` int returns. Zero floats, zero GError hot paths.
The order below puts the kinds the trace actually hits first.

**Phase 0 — measurement.** Bench harness lands first (`examples/draw-bench/`)
covering calls (extend), closures, fields, props. Run all three backends
(`jit` / `ffi` / `gi`) in separate subprocesses. Numbers gate the rest of
this plan: anything we specialize must show up.

**Phase 1 — BOOL + GOBJECT-self.** The dominant shape `(self_GObject, bool) → void`
covers `set_enabled` and the rest of the action-toggle hot path. Specialize
bool unmarshal (`PyObject_IsTrue` is one C call, no kind switch) and the
GObject-self unwrap. Void return needs no marshal helper at all.

**Phase 2 — UTF8 / UTF8_OWNED.** Every `set_label`/`set_title`/`set_subtitle`/
`set_tooltip_text` hits this. `Py_None → NULL` fast path + `PyUnicode_AsUTF8AndSize`.
Owned variant adds a `g_strdup`. Inline the `Py_None` check; the unicode
path stays a direct call.

**Phase 3 — GOBJECT wrap/unwrap.** Return path of `lookup_action`, `get_nth_page`,
arg of `page_num`. Inline the `pygir_unwrap_gobject` fast path (typecheck +
field load); slow path stays a call. Wrap goes through `pygir_wrap_gobject` —
inlining the cached PyTypeObject lookup is the win.

**Phase 4 — INT32 round trip.** `get_current_page`, `get_width`, `get_height`,
`page_num`. New `emit_unmarshal_int32` / `emit_marshal_int32` in each arch
backend. Drop `h_int32_to_py` / `h_py_to_int32` from the helper table.

**Phase 5 — INT64, UINT32, UINT64.** Same pattern as INT32; share emit
code via small inline helpers (`emit_pylong_as_intN`).

**Phase 6 — narrow ints (INT8/UINT8/INT16/UINT16).** Specialize the
widening logic that today goes through `PYGIR_SIG_RET_WIDEN_*` flags.

**Phase 7 — FLOAT/DOUBLE.** Trace shows zero floats in GUI hot paths;
do this only after the above ship and bench shows it matters.

**Phase 8 — `h_check_arg_type` removal.** Once each kind has a specialized
unmarshal, the type check fuses into the unmarshal sequence (e.g.,
`PyLong_Check` is the cmp before PyLong_AsLong). Remove the standalone
`check_arg_type` helper and the `EMIT_ERR_PROBE` after it.

**Phase 9 — GList/GSList of GObject (return only).** Trace shows
`Notebook.get_children()` returning `GList<Widget>`. Not in `PygirTypeKind`
today; the narrow JIT can't even express this shape. Either extend the
narrow JIT with a new kind or rely on the full JIT path.

After phase 7 the helper table contains only `pyerr_occurred` (and maybe
the argv pack/unpack helpers, which aren't per-kind). At that point
`pygir_jit_marshal_helper_for` / `_unmarshal_helper_for` /
`h_check_arg_type` are gone — three of the four hot generic functions.
The fourth (`x86_64_sysv_emit` itself) stays, but its inner kind switch
delegates to per-kind emitters rather than building a helper table.

## Risks

- **Code-page bloat.** Inlining everywhere blows up emitted bytes per
  trampoline; today many trampolines fit in a single page. Need to keep
  total emitted size < ~1 KiB per trampoline as a soft cap; benchmark
  instruction-cache behavior on a real GTK app, not just the microbench.
- **Per-arch duplication.** Three arches × ~12 kinds × 2 directions = 72
  emit functions. Mitigate by keeping kind→bytecode tables where possible
  (e.g., narrow-int widening is just `movsx` / `movzx` opcodes that vary
  by width).
- **CPython API stability.** Direct calls to `PyLong_FromLong` etc. bypass
  our wrapper; if CPython retires one (e.g., the long deprecation path) we
  patch the emit, not a single helper. Track per CPython minor.

## Bench-typelib extensions (gating closure/field/prop benches)

The current `packages/typelib/` GoiBench surface exposes only no-op functions.
The new bench scripts under `examples/draw-bench/` skip cleanly when the
required types are absent:

- **`PygirBench.Object`** — a `GObject` subclass with:
  - signal `tick` (no args, no return) — drives `closure_bench.py`
  - int property `value` — drives `prop_bench.py`
  - method `tick()` that emits the signal
- **`PygirBench.Box`** — a refcounted boxed struct with:
  - `gint a; gint64 b; gdouble c;`
  - `pygir_bench_box_new ()`, `_copy`, `_free`
  - `G_DEFINE_BOXED_TYPE` so it gets a GType — drives `field_bench.py`

Both fit in ~80 lines of straightforward GObject boilerplate in
`bench.c` / `bench.h`, plus a meson regen of the `.goi` / `.typelib`.
Land them as a separate change; the bench scripts auto-pick them up.

## Non-goals

- No new ABIs. x86_64 SysV / aarch64 SysV / ia32 cdecl only, same as today.
- No on-the-fly recompilation. Specialization is fully pre-determined at
  descriptor build time.
- No PIC / position-independent indirection optimization. RIP-relative
  loads through the per-trampoline table stay; the win is removing the
  *helper* call, not the table itself.
