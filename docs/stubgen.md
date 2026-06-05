# Type stub generation (`.pyi`)

How we generate PEP 561 type stubs for the dynamically-built GI namespaces,
where we stand relative to the third-party
[`pygobject/pygobject-stubs`](https://github.com/pygobject/pygobject-stubs),
and what is still missing.

This was last reviewed against `pygobject-stubs` master in May 2026.

> **Status (May 2026).** The generator now lives in `packages/ginext-stubgen`
> (module `ginext_stubgen`), emits two modes — `native` (the `from ginext import
> <NS>` surface) and `gi` (the `gi.repository` compat layer) — and ships **typed
> GObject signals**. Native stubs are delivered as the separate PEP 561
> `packages/ginext-stubs` distribution. This document reflects that state.

## Two ways to build stubs

There are two fundamentally different strategies, and we and the upstream
project picked opposite ones:

| | source of truth | sees gtk-doc | sees runtime overrides | needs libs at gen time |
|---|---|---|---|---|
| **ours** (`packages/ginext-stubgen`) | GIR **XML** (`*.gir`) | yes | only via explicit overlays | no — parses XML |
| **pygobject-stubs** | **runtime** introspection (`gi.repository` + `gi.GIRepository`) | no | yes (it imports the module) | yes |

The GIR-XML route gives us documentation and a complete static view (including
things PyGObject hides), at the cost of having to re-apply PyGObject's runtime
overrides ourselves. The runtime route automatically reflects whatever the
imported module actually exposes, but loses the gtk-doc text and depends on the
libraries being installed and importable.

## `pygobject-stubs` (the baseline)

Generator lives in `src/pygobject_stub_generator/` (a PEP 517 backend that runs
at build time): `parse.py`, `class_info.py`, `arguments.py`, `property_info.py`,
`type_var_info.py`, `stub.py`. The checked-in repository stubs under
`src/gi-stubs/repository/*.pyi` are the generated output.

What it types well:

- **Properties** — an inner `class Props:` per object plus a typed
  `def __init__(self, *, prop: T = ..., ...)` so `Label(label="hi")` checks.
- **Callback *parameters*** — concrete `Callable[[ArgT, ...], RetT]`, and — its
  one genuinely sophisticated trick — it ties a function's `*user_data` to the
  callback's trailing parameters through a `TypeVarTuple` (`type_var_info.py`):

  ```python
  def idle_add(
      function: Callable[[Unpack[_DataTs]], bool | None],
      *user_data: Unpack[_DataTs],
      priority: int = ...,
  ) -> int: ...
  ```
- **Generics** — `Gio.ListStore[T]` etc. via real `TypeVar`s.
- **vfuncs** on classes (`do_*`), out-params folded into tuple returns.

What it does **not** do:

- **Signals are untyped.** `connect`/`connect_after`/`emit` are the
  lowest-common-denominator generic:

  ```python
  def connect(self, signal_name: str, callback: Callable[..., Any], /, *user_data: object) -> int: ...
  def emit(self, signal_name: str, /, *args: object) -> Any: ...
  ```

  No `Literal["clicked"]` overloads, no per-signal handler argument types. A
  checker can't validate a handler's signature or the signal name.
- **No docstrings** (open issue [#76]).
- **vfuncs on *interfaces*** are missing (open issue [#219]).
- **No deprecation surfacing** (PEP 702 `@deprecated`, open issue [#165]).

Open issues worth tracking (May 2026): generic callback breakage on
`Gtk.ListBox` sort/filter ([#311]); `Gtk.WidgetClass` methods that shadow
`Gtk.Widget` can't be classmethods ([#184]); invalid Python emitted for some
Gtk3 stubs ([#169]); `GLib.option` placeholder ([#148]).

## Our stubgen (`packages/ginext-stubgen`)

Architecture: `Parser` (GIR XML → small dataclass IR — `Namespace`, `Klass`,
`Callable`, `Param`, `Property`, `Enum`, `Constant`, `Alias`, `CallbackType`,
`Signal`) then `Emitter` (IR → `.pyi` text). Entry point
`generate(gir_path, mode=...)`; `__main__.py` / the `ginext-stubgen` console
script drive a batch. Two `mode`s select the import root: `native` (`from ginext
import <NS>`, default — written to the `ginext-stubs` package as unsuffixed
`<NS>.pyi`) and `gi` (`from gi.repository import <NS>` — version-suffixed
`<NS><major>.pyi` + `<NS>.pyi` symlink, for the compat layer).

Currently emitted:

- Top-level **functions**, **constants**, **aliases**.
- **Enums / bitfields** → `IntEnum` / `IntFlag` (digit-leading members prefixed
  `_`).
- **Classes / interfaces / records / unions**:
  - constructors: `new` → `__init__` + `@classmethod new(...) -> Self`; others →
    `@classmethod ... -> Self`;
  - instance **methods**, static functions, **properties** (flat class-level
    annotations; record/union fields too);
  - **vfuncs** → `do_<name>` — including on **interfaces**.
  - **signals** (`<glib:signal>`) → native: typed `obj.<signal>` descriptors
    (`_Signal`/`_SignalMethod`); compat: `Literal`-keyed `connect` overloads;
    `do_<signal>` in both (see "Typed signals" below).
- **Callbacks** → typed `Name = Callable[[ArgT, ...], RetT]` aliases.
- **Out / inout params** folded into `tuple[ret, out1, ...]` returns.
- **Container element types**: `GLib.List/SList/Array/PtrArray` → `list[T]`,
  `HashTable` → `dict[K, V]`, `Bytes/ByteArray` → `bytes`.
- **Nullability**: nullable in-params → `T | None = ...`; nullable returns →
  `T | None`; optional-before-required reordering fixed up.
- **Keyword/builtin sanitisation**: `in` → `in_`, shadowed builtins → `name_`.
- **`shadowed-by`** inversion (emit the user-visible name with the
  introspectable companion's signature), for both methods and functions.
- **`GType`** → `type | GObject.Type`.
- **gtk-doc → reStructuredText docstrings** (PyCharm-oriented), with C-symbol
  cross-references rewritten to the Python surface.
- **`GLibUnix`** merged into `GLib` (`unix_*`).

### Typed signals

The native and compat surfaces are deliberately different, because the native
runtime signal API *is* different.

**Native** — signals are accessed as `obj.<signal>` (a descriptor), never via a
string `connect("name", …)` (that's PyGObject-compat). The runtime exposes each
signal as a combined object that connects/emits and, for an **action** signal
(`G_SIGNAL_ACTION`), is also callable-to-emit (`button.clicked()`); callability
comes from the signal's flags (introspection), not an overlay — see the runtime
`Signal.__call__` / `private.signal_is_action`. So the emitter gives each signal
a typed descriptor attribute:

- action signal → `_SignalMethod[Owner, P, R]` — `connect(handler:
  Callable[[Owner, *P], R])`, `emit(*P) -> R`, **and** `__call__(*P) -> R`.
- plain signal → `_Signal[Owner, P, R]` — connect/connect_after/emit only.

The `_Signal`/`_SignalMethod` generics (`Generic` + `ParamSpec` + `Concatenate`;
`ParamSpec` is aliased to dodge GObject's own `ParamSpec`) are emitted in each
native stub's header. A signal whose name collides with a method on the class or
an ancestor (e.g. `Gtk.Widget.activate`) keeps the method — the descriptor is
skipped so it doesn't shadow it. `do_<signal>` default handlers are emitted too.

**Compat (`gi`)** — keeps the legacy string-keyed API: per-signal `@overload`s
of `connect`/`connect_after`/`emit` on `Literal["name"]` plus a generic
`connect(self, signal: str, handler: Callable[..., Any], *args)` catch-all (so
inherited and detailed `"notify::label"` names still check, permissively).

Every generated stub carries `# mypy: disable-error-code="override"`: GI's heavy
multiple inheritance makes these overloads (and routinely-refined methods) read
as incompatible overrides, which mypy anchors to the class line across the MRO
where a per-line `# type: ignore` can't reach. The overrides are intentional and
runtime-correct.

### Generics

GIR doesn't express element types, so item-typed list models are curated
declaratively in `native_overlays.toml`: a class carries `item_type = "_T"`
(generic over its element) or `item_type = "Gtk.StringObject"` (concrete). The
emitter (`_apply_item_type`) then auto-parameterizes the GIR-derived members —
rewrites the item's `GObject.Object` returns/params to the element type,
`get_item_type` / the `item-type` property to `type[<item>]`, the implemented
`Gio.ListModel` base to `Gio.ListModel[<item>]`, and (for generic models) the
wrapped-model accessors and the class's own type, so e.g.
`FilterListModel.new(model) -> FilterListModel[_T]`. The element `TypeVar` has a
PEP 696 default of its bound (`GObject.Object`), so a bare `Gio.ListStore`
resolves to `Gio.ListStore[GObject.Object]` — the common base, never `Any` (and
no `[Any]`-appending hack).

Coverage: `Gio.ListModel`/`ListStore` plus the ~18 Gtk classes implementing
`Gio.ListModel` — generic wrappers/selections (`Filter`/`Sort`/`Slice`/`Flatten`/
`Map`/`SelectionFilter`ListModel, `Single`/`Multi`/`NoSelection`) and concrete
containers (`StringList`, `DirectoryList`, `BookmarkList`, `MultiFilter`/`Any`/
`Every`, `MultiSorter`, `TreeListModel`). `pygobject-stubs` does only the two Gio
ones. Real inference verified: `store: Gio.ListStore[Gtk.Button]` rejects
`store.append(Gtk.Label())`, and `store.get_item(0)` is `Gtk.Button | None`.

Tricky members (e.g. `ListStore.new(item_type: type[_T])`, whose `GType` arg
must link to `_T`) keep a hand-written `body`/`reserves` override.

### Overlay system

The generator stays free of hand-written Python source by layering declarative
TOML overlays:

- `native_overlays.toml` — module preludes and hand-written class bodies for
  surface installed via C type slots (e.g. `GObject.Object.connect/emit/props`,
  the `_PropsProxy` helper, `GObject.Type`), plus a `reserves` list that
  suppresses GIR-derived re-emission of those names. Always applied.
- `native_mode_overlays.toml` — `mode="native"` deltas (the `GObject.Signal` /
  `GObject.Property` descriptor stubs, the async `Gio.File` surface).
- `src/ginext/_overlays/<NS>-<v>.toml` — per-namespace `alias` / `internal` /
  `class` transforms (add a property from a getter's return type, bind a method
  to a top-level function's signature). This is the place to "fill in" overlays.

The runtime overlays (`src/ginext/_overlays/*.py`, the per-package
`_overlays/*.py`) use the imperative `overlay.X(...)` registration API and are
**not** consumed by the generator yet — reflecting them into stubs is a future
feature.

## Where we stand vs `pygobject-stubs`

**Ahead**

- **Docstrings.** We convert gtk-doc to RST and attach it to classes, methods,
  constants. `pygobject-stubs` has none ([#76]).
- **Interface vfuncs.** Our `do_*` emission covers interfaces, the gap behind
  their [#219].
- **No runtime dependency.** We parse `.gir`, so generation doesn't need the
  libraries importable, and can't be tripped by import-time failures.
- **Typed signals.** Native models the real `obj.<signal>.connect(handler)` API
  with typed `_Signal`/`_SignalMethod` descriptors (handler and emit/return
  types enforced); compat keeps a typed string-`connect` form. `pygobject-stubs`
  has neither — its `connect` is `Callable[..., Any]`. See "Typed signals".
- **Typed construction.** GObject `__init__` is keyword-only over the class's
  *writable* properties — `def __init__(self, *, label: str = ..., ...,
  **kwargs: Any)` — so `Gtk.Button(label=5)` is a type error while unknown /
  inherited props fall to `**kwargs`. Properties are also flat attributes
  (`label: str`), so `widget.label` reads/writes type-check (ginext synthesises
  descriptors, unlike PyGObject's `.props.x`-only model).

**At parity**

- Callback *parameter* types, out→tuple folding, nullability widening,
  keyword-name sanitisation, container element types, `IntEnum`/`IntFlag`.

- **Generics.** `pygobject-stubs` makes only `Gio.ListModel`/`ListStore`
  generic; we cover those plus the whole Gtk list-model family (~18 classes) —
  generic wrappers (`FilterListModel`, `SortListModel`, selections, …) and
  concrete-item containers (`StringList → StringObject`, `DirectoryList →
  Gio.FileInfo`, …). See "Generics" below.

**Behind**

- **`TypeVarTuple` user_data linkage.** We *elide* the `closure`/`destroy`/array
  -length companions entirely (matching PyGObject's runtime), so passing
  `*user_data` is untyped. They keep it and tie it to the callback via
  `Unpack[_DataTs]`.

## Relationship to the runtime `__signature__`

`src/ginext/signature.py` is the **runtime** analogue of the stubgen's static
type logic: it builds `inspect.Signature` objects on demand from
`GIRepository` info so `inspect.signature(fn)` / `help()` / IDEs work without a
`.pyi`. The two implementations independently encode the same rules — keyword
sanitisation, callback-companion elision, out/inout → `tuple[...]`, nullable →
`T | None`, callback args → `Callable[[...], ret]` — and should be kept in sync
(e.g. `signature.py` degrades unresolved `GType` to `Any`, while the stubgen
emits `type | GObject.Type`). Core coverage lives in
`src/ginext/tests/test_signature.py`.

## Missing / roadmap

1. **Switch the repo itself onto `ginext-stubs`.** Today `ginext-stubs` is a
   standalone artifact, intentionally not in the uv workspace: installing it
   would let mypy discover it and shadow `src/ginext`'s inline `Namespace`-based
   typing (`.overlay` etc.), breaking `make typecheck`. Migrating the repo to
   consume the generated namespace stubs (and trimming `src/ginext/__init__.pyi`)
   is a separate, careful step.
2. **`TypeVarTuple` user_data** — optionally surface and link `*user_data`
   instead of eliding it, to match `idle_add` & friends.
3. **PEP 702 `@deprecated`** from GIR `deprecated="1"` (their [#165]; we don't
   do it either).
4. **Per-package overlay TOML discovery.** `load_overlay_toml` only looks under
   `src/ginext/_overlays/`; namespaces owned by `packages/*` (Gtk, Gio, …) can't
   yet carry per-namespace overlays, and the imperative runtime overlays aren't
   reflected into stubs.
5. **Broader / pinned namespace coverage** for the shipped `ginext-stubs`
   (currently the GTK4 closure), and regenerate-in-CI to prevent drift.
6. **Stricter signal handlers** without false-positives on inherited/detailed
   signals (would need the full inherited signal set per class).
7. **Compat-mode (`gi`) parity**, incl. the per-class `Props` proxy typing
   (compat-only) reverted from native in `aa8050c8`.

[#311]: https://github.com/pygobject/pygobject-stubs/issues/311
[#219]: https://github.com/pygobject/pygobject-stubs/issues/219
[#184]: https://github.com/pygobject/pygobject-stubs/issues/184
[#169]: https://github.com/pygobject/pygobject-stubs/issues/169
[#165]: https://github.com/pygobject/pygobject-stubs/issues/165
[#148]: https://github.com/pygobject/pygobject-stubs/issues/148
[#76]: https://github.com/pygobject/pygobject-stubs/issues/76
