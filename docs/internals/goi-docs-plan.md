# Runtime docstrings for goi (`.goidoc` plan)

Design doc for surfacing GIR `<doc>` text through Python's standard
documentation mechanisms (`help()`, `pydoc`, `inspect.getdoc`, IDE
hovers) without bloating `_goi.so` or slowing imports.

## Goal

User-visible behaviour we want to enable:

- `help(Gtk.Window)` — class doc + each method's doc.
- `Gtk.Window.set_title.__doc__` — returns the GIR doc text.
- `pydoc gi.repository.Gtk` — walks the module, finds docs.
- IDE hover (VS Code, PyCharm, Helix), mypy `--show-error-context`,
  pyright hover — pick up docs from the `.pyi`.

## Constraints

- `_goi.so` carries zero docstring text. Docs are namespace-scale data
  (~3 MB per namespace once de-duplicated and compressed) and the same
  C build serves every distro.
- Importing `goi.repository.Gtk` reads no docs. Only first access to a
  `__doc__` attribute triggers a load — and even then only of the one
  namespace whose doc is being touched.
- Disk: a sidecar file per namespace is fine. GIR XML is ~4 MB on
  disk; extracting just the doc text and packing it compactly gets us
  below 3 MB per namespace.

## Architecture — three layers

### 1. Docstrings in `.pyi` (free, IDE-only)

Stubgen extracts `<doc>` text from each `<class>`, `<interface>`,
`<record>`, `<union>`, `<method>`, `<constructor>`, `<function>`,
`<property>`, `<enumeration>`, `<bitfield>` and emits them as
triple-quoted docstrings in the `.pyi`.

IDEs, mypy/pyright/ty hover, and `pydoc <module-imported-as-stub>`
pick them up. Zero runtime cost — `.pyi` files are never imported at
runtime, and the doc text is the source of truth for layer 2 below
(same generator pass, no drift risk).

### 2. `.goidoc` binary sidecar (runtime, lazy)

One file per `(namespace, version)`, shipped next to the `.pyi`:

```
src/goi/repository/Gtk-4.0.goidoc
src/goi/repository/GLib-2.0.goidoc
src/goi/repository/Gio-2.0.goidoc
…
```

mmap'd on first access, paged in by the OS as docs get read. Zero
memory footprint for unused docs. Binary-searchable index, no
parsing.

Format:

```
Header (32 bytes):
  magic        "GOIDOC\0\0"     (8 bytes)
  version      uint32           (1 for now)
  namespace    char[16]         (NUL-padded ASCII)
  index_count  uint32
  strings_off  uint32

Index (sorted by key bytes for binary search, 12 bytes/entry):
  key_off      uint32           → into strings blob, NUL-terminated key
  doc_off      uint32           → into strings blob, NUL-terminated doc text
  doc_len      uint32           (length of doc text in bytes, excluding NUL)

Strings blob:
  Concatenated NUL-terminated UTF-8 strings.
```

Key conventions:
- Class members: `"ClassName.method"`, `"ClassName.constructor"`,
  `"ClassName.property"`.
- Class itself: `"ClassName"`.
- Top-level functions: `".function_name"` (leading dot disambiguates
  from class names).
- Namespace itself: `""` (empty key).
- Enum members: `"EnumName.MEMBER"`.

Size on disk for commander's 9 namespaces, very roughly: header +
index ~50 KB, strings ~3 MB total. Versus ~5 MB if we shipped a `.py`
dict — but the `.py` would all be paged in, the `.goidoc` is paged in
by the OS only where the user actually reads.

Lookup is O(log n) binary search on the mmap; no parse, no
allocation. First mmap is ~50 µs; subsequent lookups ~5 µs.

### 3. `__doc__` as a descriptor at every layer

Python's attribute lookup machinery already supports `__doc__` as a
property — replace the static slot with a getset that calls into
`goi.docs.lookup(...)` lazily. `help()`, `pydoc`, `inspect.getdoc()`,
REPL `obj.method?` all go through the same path, so the descriptor
serves them all.

- **Methods (`MethodDescriptor`)**: `__doc__` is a slot on the
  descriptor type. Replace its static `tp_doc` with a `PyGetSetDef`
  entry — `method_descriptor_get_doc` runs on `method.__doc__` access
  and returns the cached string from `goi.docs.lookup`.
- **Classes (heap types via `PyType_FromSpec`)**: install a
  descriptor on the metaclass for `__doc__`. `type.__getattribute__`
  finds the descriptor on the metaclass, calls it bound to the class.
  Works for `Gtk.Window.__doc__` and `help(Gtk.Window)`.
  *Alternative:* eager populate `tp_doc` at namespace-open time
  (string lookup per class, then `PyType_Modified`). Eager but
  tiny — saves us adding a metaclass. **Pick this for v1**.
- **Namespace modules (`goi.repository.Gtk`)**: extend the existing
  PEP 562 `__getattr__` to handle `"__doc__"` — call into
  `goi.docs.lookup(ns, "")`.
- **Property descriptors (`obj.props.label.__doc__`)**: `_PropsProxy`
  already proxies attribute access; route `__doc__` reads here too.
  Lower priority — most users `help()` the class, not individual
  property entries.

## Implementation order

1. **`tools/stubgen/goidoc.py`** (~80 lines). Walks `<doc>` elements
   per namespace, deduplicates blobs, sorts the index by key, writes
   the binary. Emit triple-quoted docstrings in the `.pyi` at the
   same time (same pass over the GIR).
2. **`src/goi/docs.py`** (~50 lines). Lazy mmap loader + binary
   search. Public surface: `lookup(namespace: str, key: str) -> str |
   None`. Caches the mmap (one per namespace) and a precomputed list
   of `(key_bytes, doc_off, doc_len)` per file.
3. **C: `MethodDescriptor.__doc__` getset** (~20 lines). Wherever
   `MethodDescriptor` is declared (`src/_goi/runtime/lazy.c` or
   similar) — add a `getset` entry routing `__doc__` reads to
   `goi.docs.lookup` via the GIL-held Python API.
4. **Eager `tp_doc` for classes at namespace-open time** (~30
   lines). When `goi.open_namespace` finishes building a
   `LazyNamespace`, iterate its already-built classes and set
   `tp_doc` from `goi.docs.lookup(ns, class_name)`. Bounded by class
   count (~hundreds per namespace), runs once.
5. **Module `__doc__`** (~5 lines). Extend
   `goi.repository.__getattr__` so `__getattr__("__doc__")` returns
   the namespace's doc.
6. **Stubs: docstrings in `.pyi`** (already done as part of step
   1). IDE hovers light up.

## Open questions / decisions

1. **Binary format**: the shape above (mmap + sorted index + strings
   blob). Confirmed; alternative was SQLite, rejected for simplicity.
2. **Class docs**: lazy via metaclass vs eager `tp_doc` install at
   namespace-open time. **Picked eager** — cost is trivial (string
   lookup per class), class count is bounded, no metaclass to add.
3. **Scope of generated docs**: methods + constructors + static
   functions + classes + module. **Enum members and property
   entries: skip for v1**. Their docs are short and rarely
   introspected; cheap to add later.
4. **File location**: `src/goi/repository/<NS>-<v>.goidoc` next to
   the `.pyi`. Stubgen writes both, wheel installs both.
5. **Wheel inclusion**: `.goidoc` files must be in
   `package_data`/`MANIFEST.in` so they survive
   `meson-python`/`hatch`/`uv build`. Verify after step 1.
6. **Generator invocation**: `python -m tools.stubgen Gtk:4.0` should
   emit both files. Add a `--no-docs` flag for callers that only want
   the `.pyi`.
7. **Caching**: `goi.docs` keeps mmaps and indices in module-level
   dicts. Process-lifetime caches; no eviction needed at this scale.
8. **Thread safety**: mmap is read-only after creation. Index list
   is built once per namespace and never mutated. No locking
   required beyond Python's normal dict access.

## Cost / risk summary

- ~3 MB per namespace shipped in the wheel. For commander's 9
  namespaces ≈ 25 MB on disk, paged in by the OS only on read.
  Trimmable later: compress strings with zstd dict (~70 % cut) at the
  cost of decompressing on lookup (~50 µs).
- `_goi.so` size: unchanged.
- Startup: unchanged. First doc access per namespace: ~50 µs.
  Subsequent: ~5 µs.
- Generator complexity: small. Doc text extraction is straightforward
  `<doc>` walking with whitespace normalisation.
- C-side complexity: one getset for `MethodDescriptor`, one
  namespace-open hook for class `tp_doc`. ~50 lines total.
- Risk: drift between `.pyi` docstrings and `.goidoc` text. Mitigated
  by generating both in the same pass from the same GIR source.

## Out of scope

- gi-docgen-quality formatting (cross-references, code-block
  rendering, etc.). The GIR `<doc>` text is plain-ish Markdown; we
  pass it through as-is. Rendering is the user's problem (`pydoc`
  shows raw text; IDEs may render Markdown).
- Translations / localisation. GIR sometimes carries language tags;
  we take the default (English) for v1.
- Deprecation notices as separate fields. GIR has
  `<doc-deprecated>` — emit as a parenthetical at the end of the doc
  text rather than a separate slot.
