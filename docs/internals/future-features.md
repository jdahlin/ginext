# Future Features — goi feature-gap punch list

A prioritized list of capabilities `goi` could add, derived from a survey of
upstream PyGObject (`pygobject/gi/{overrides,_gtktemplate.py,_propertyhelper.py,events.py,pygi-async.c,...}`).

Sizes: **S** = afternoon, **M** = days, **L** = subsystem.
Coverage labels apply to upstream PyGObject:
*none* / *partial* / *awkward*.

---

## 1. GtkBuilder / Gtk.Template

- **`<closure>` element under widget properties** — *none*. PyGObject's
  `_gtktemplate.define_builder_scope` only resolves callback names; expression
  children are silently discarded. Pinned today by xfailed
  `tests/test_gtk4_template_closure.py`. **M**
- **`Gtk.Expression` family** (`PropertyExpression`, `ConstantExpression`,
  `ClosureExpression`) — *none*. No override in `overrides/Gtk.py`; no Pythonic
  chaining or lambda → ClosureExpression conversion. **L**
- **`Gtk.BuilderListItemFactory`** — *none*. Modern list views require it; no
  `@Gtk.Template` integration. **M**
- **`Gtk.SignalListItemFactory`** — *awkward*. No decorator that wires
  `setup`/`bind`/`unbind`/`teardown` from one class. **S–M**
- **Public `Gtk.BuilderScope` subclass** — *partial*.
  `Builder(scope_object_or_map=...)` exists but rejects
  `BuilderClosureFlags.SWAPPED`. **S**
- **Inheritance from `@Gtk.Template`-decorated classes** — explicitly rejected
  (`_gtktemplate.py:165`). **M**
- **Custom `<child type=...>` / `buildable_custom_tag_start` parser hooks** —
  *none*. **L**
- **`init_template` walks only `cls.__dict__`** — child resolution silently
  breaks across an inheritance layer.

## 2. Newer GTK / Gdk / Gst / libadwaita / GIO (≈2021–2026)

- **`async`/`await` on `*_async`/`*_finish` pairs** — *partial*. PyGObject's
  `pygi-async.c` provides one generic awaitable; no per-method auto-rewrite. **M**
- **`Gio.Subprocess` / `SubprocessLauncher`** — *none*. **M**
- **`Gdk.ContentProvider` / `Clipboard` / `Drop` (GTK4 redesign)** — *none*;
  `overrides/Gdk.py` is still GTK3-flavored. **L**
- **`Gsk` render nodes** — *none*. `do_snapshot` requires raw vfunc usage. **M**
- **`Gdk.Toplevel` / `Surface` / `Monitor`** — *none*. **M**
- **libadwaita** — *none*; PyGObject ships no `overrides/Adw.py` at all
  (Adw.MessageDialog/AlertDialog async, ToastOverlay, ComboRow, etc.). **M–L**
- **GStreamer** (`Gst.Promise`, playbin3, bus ↔ asyncio) — *none* override
  module. **L**
- **`Gio.ListStore[Gio.File]()` setting `item_type`** — *partial*. Generic
  typing exists but `__class_getitem__` doesn't set runtime `item_type`. **S**
- **`Gtk.CustomFilter`** wrapper — *none* (CustomSorter has one). **S**
- **`Gio.DBusObjectManager`** server/client overrides — *none*. **M**
- **`Gtk.Shortcut`/`ShortcutController` declarative class-body helper** —
  *none*. **S–M**

## 3. Python ecosystem (≈last 10 years)

- **PEP 561 `.pyi` stubs** — PyGObject ships none; offloaded to community
  `pygobject-stubs`. **L**
- **PEP 526 annotation → `Property` type inference** — *none*.
  `prop: int = GObject.Property()` doesn't infer;
  `_propertyhelper._type_from_python` ignores annotations. **S**
- **`@dataclass` interop with `GObject.Property`** — *none*. **M**
- **`__init_subclass__` user hook for GObject classes** — *partial*. PyGObject
  does it in the C metaclass and doesn't expose it. (goi already lays
  groundwork in commit `9f614e8`.) **M**
- **`__class_getitem__` setting runtime `item_type`** — *partial*; only
  type-checker, not runtime. **S**
- **PEP 688 buffer protocol on `GLib.Bytes`** — *partial*. Returns `bytes`; no
  zero-copy NumPy/cairo interop. **M**
- **`inspect.Signature` for introspected callables** — *partial*; PyGObject's
  `_signature.py` is recent and not wired into vfuncs/signals. **S**
- **PEP 657 fine-grained tracebacks** through closure marshalling — Python
  frame context lost. **M**
- **PEP 703 free-threaded CPython** — PyGObject is not nogil-safe;
  `pygi-closure.c` / `pygi-async.c` rely on hard GIL state. **L**
- **`contextvars` propagation through asyncio ↔ GLib bridge** — *partial*;
  `events.py:264` doesn't propagate context to idle dispatch. **M**
- **`StrEnum` / `IntFlag`** — *partial*; `_enum.py` builds IntEnum-like, `|`
  returns plain `int` in some paths. **S**
- **Async iteration on `FileEnumerator`** (`__aiter__` via
  `next_files_async`) — *none*. **S**
- **`os.PathLike` coercion in `Gio.File.new_for_path`** — *partial* (no
  `os.fspath`). **S**
- **`__match_args__` on `GLib.Variant` / enums for pattern matching** —
  *none*. **S**
- **`weakref.finalize` for boxed cleanup** instead of `__del__` — *none*. **S**

## 4. Linux platform

- **`io_uring` `MainContext` backend** (GLib 2.80+) — no Python knob. **M**
- **`pidfd` / `eventfd` / `signalfd` GSource wrappers** — *none*; PyGObject's
  `events.py` only does `add_unix_fd`. **S–M**
- **xdg-desktop-portal / `libportal`** — *none*; no override despite the
  library shipping its own GIR. **M**
- **systemd: `sd_notify`, `sd_listen_fds`, journal** — *none*. **S–M**
- **Wayland-specific** (`GdkWayland.WaylandToplevel.export_handle`,
  xdg-foreign) — *none* at override level. **S**
- **cgroups v2 / launching `Gio.Subprocess` into a systemd transient scope** —
  *none*. **M**
- **`fanotify` beyond `Gio.FileMonitor`** — *none*. **S**

---

## Top punch-list for goi

1. **`Gtk.Expression` + `<closure>` / `<lookup>` template plumbing** — biggest
   single GTK4 gap; unblocks list views, `Adw.PropertyRow`, etc.
2. **Auto-`await` on every `*_async` / `*_finish` pair** at the binding level.
3. **PEP 561 `py.typed` + generated `.pyi`** from GIR.
4. **`overrides/Adw.py` and `overrides/Gst.py`** — PyGObject ships neither.
5. **`Gio.ListStore[T]()` runtime `item_type`** + **`Property` inferring type
   from PEP 526 annotation.** (Two tiny S-class wins.)
6. **`@dataclass`-style class body** for properties/signals via
   `__init_subclass__` (extend the in-progress work to dataclass interop).
7. **`GLib.Bytes` PEP 688 buffer protocol** for zero-copy cairo/numpy.
8. **xdg-desktop-portal helper module** — high impact for Flatpak.
9. **`io_uring` / `pidfd` / `eventfd` GSource wrappers** in the asyncio bridge.
10. **Free-threaded (3.13t / 3.14t) audit** of closure invocation + Async
    object.
