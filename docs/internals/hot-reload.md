# Hot reload for GObject subclasses

## Motivation

Long-running GTK Python apps can't `importlib.reload(module)` and keep going
the way pure-Python apps can. The blockers are well-known and have killed
every PyGObject attempt:

- `GType` names are registered globally per process. The second class body
  with the same `__gtype_name__` either fails or silently re-binds against
  the old GType.
- Live widget instances reference their type via a C pointer in the GObject
  struct. Swapping the Python class doesn't move existing instances; GTK
  keeps dispatching through the old vfuncs.
- vfunc overrides are patched into the parent GType's class struct.
  Replacing the class doesn't un-patch them, so a `do_activate` removed in
  the new code keeps running from the old code.
- Signals, properties, and template metadata are registered against the
  GType. Re-registering aborts; not re-registering leaves stale handler
  refs.

PyGObject couldn't solve these because its design predates the levers
needed. goi controls every one of them — class building, type registry,
vfunc install path, per-instance wrapper qdata — so reload is in scope here
in a way it isn't anywhere else.

The goal is `goi.reload_module(mod)`: edit a file, hit save, the running
GTK app picks up the new code without restarting. Window position, focus,
scroll state, untouched widgets all stay alive. For the docviewer this
means each runnable example morphs in place instead of `kill -TERM` →
respawn.

## What already works in goi

`goi_gobject_base_init_subclass` (`src/_goi/GObject/Object-metaclass.c`)
already half-handles re-imports:

```c
GType existing = g_type_from_name (name);
if (existing != 0) {
    if (g_type_is_a (existing, parent_gt)) {
        goi_class_registry_set (cls, existing, parent_info, NULL);
        Py_RETURN_NONE;
    }
    ...
}
```

If the GType name already exists and descends from the same parent, it
re-keys the registry so the *new* Python class is what
`goi_class_registry_get_pytype_for_gtype()` returns. Future C-returned
instances of that GType then come back as the new class.

What's missing: existing instances stay on the old class, and overrides
from the old class remain in the GType's vtable. The full reload story
fills those gaps.

## Architecture — three pieces

### 1. Instance walk + `__class__` swap

goi tags every GObject wrapper with a qdata key
(`goi_gobject_wrapper_quark()`, `Object-wrap.c`). That's enough to walk
every live wrapper of a given GType.

On reload:

1. Look up the GType being re-keyed.
2. Walk all objects of that GType — use `g_object_get_qdata` from a
   gtype-to-instances index goi maintains, or fall back to
   `g_type_class_peek` + a custom registry of wrappers per type.
3. For each wrapper, `Py_SET_TYPE(wrapper, new_class)` and `Py_INCREF` the
   new class / `Py_DECREF` the old. CPython requires `tp_basicsize` to
   match — guaranteed here because every GObject wrapper goi builds shares
   the same heap-type layout (`GoiGObjectObject`).

The wrappers-per-type index doesn't exist yet. The minimum addition is a
`GHashTable<GType, GHashTable<wrapper *, NULL>>`, populated at
`goi_gobject_register_wrapper` and pruned at dealloc. ~30 lines in
`Object-wrap.c`. Cost: one extra hash insert/remove per wrapper construction
— measure, but well under 100 ns.

Alternative: walk all GObjects via `g_type_class_peek_static` and
`g_type_class_get_instance_private` — too brittle, GLib doesn't expose
instance iteration as a stable API. The wrappers-per-type index is the
sound path.

### 2. vfunc vtable snapshot + restore

`goi_gobject_install_vfunc_overrides` (`Object-vfunc.c`) patches `do_*`
methods into the GType's class struct. On reload we need:

- **Snapshot** the parent's original vtable entries on the *first*
  override install per GType. Stash on the class registry entry as
  `original_vtable_slots`.
- **Restore from snapshot** on reload before re-installing. Slots removed
  in the new class go back to the parent's default; slots still present
  get re-patched with the new Python function.

The snapshot has to be selective. We only own slots we've patched, not
slots GTK itself overrode at class init. The bookkeeping: per
`GoiClassEntry`, a `GHashTable<offset_in_class_struct, original_fn_ptr>`
keyed by vfunc slot offset, populated on first install, consulted on
reload.

Snapshot lives forever — we can never know for sure that another binding
or library doesn't also want to override the same slot. Reload only
restores slots *we* installed.

### 3. Signal-handler tracking + disconnect

When module code runs `obj.connect("clicked", on_click)`, GObject stashes
a closure that holds a strong ref to `on_click` — a Python function from
the soon-to-be-stale module. Re-executing the module body re-runs the
`.connect(...)` calls, so after reload the object has *both* the old and
new handlers, with the old ones referencing the dead module.

`g_signal_handlers_disconnect_by_func` exists but takes a C function
pointer; it can't disconnect by "all handlers whose closures were
created from Python module X." That distinction has to come from goi.

The mechanism:

- **Track on connect.** goi's `obj.connect()` overlay already wraps
  `g_signal_connect_data` (it has to, for `trailing_user_data`). Extend
  it to record an entry per call, keyed by the *caller's* module
  (read from `PyEval_GetFrame()->f_code->co_filename` → module name).

  Keying by the *connecting site* (not the callback's module) gives
  the natural semantics: when you reload the file whose body wrote
  `obj.connect(...)`, that connect re-fires from the new body —
  regardless of where the callback function itself lives.

  ```c
  struct GoiConnectRecord {
      GWeakRef target;     // the GObject — weak so dealloc doesn't leak
      gulong  handler_id;
      // caller-module name is the dict key, not stored per record
  };
  ```

- **Disconnect on reload.** `goi.reload_module(mod)` walks
  `connect_registry[mod.__name__]`, calls
  `g_signal_handler_disconnect(target, handler_id)` for each live
  target, then drops the list. The module's body re-runs and the new
  `.connect(...)` calls repopulate it.

- **Template handlers**: `Gtk.Template.Callback` routes through goi's
  `BuilderScope.do_create_closure` (`Template.py`). That's where the
  callback closure for `<signal handler="...">` gets built — add the
  same registry insert there, keyed on the template class's module.

- **What we don't track**: handlers connected from C code (e.g. Adw's
  internal wiring), handlers connected via `connect_object` (those
  auto-disconnect on the linked object's destroy, so leaking them is
  not the concern), and handlers whose callback can't be associated
  with a module (lambdas, partials wrapping C funcs).

Lifetime detail: we use `GWeakRef` so a destroyed GObject doesn't pin
the registry entry alive. The reload sweep skips entries whose weakref
returns NULL and frees them.

Cost on connect: one hash lookup + one list append per call. Connect is
already not on any hot path — adwaita button widgets connect a handful
of signals at startup and then dispatch through C. Won't be measurable.

### 4. Idempotent re-registration

Signals, properties, GResource templates: these all call
`g_signal_new` / `g_object_class_install_property` /
`gtk_widget_class_set_template`. Re-running them on the same GType is
either an error or duplicate registration.

The fix is shape-check on each path:

- `goi_gobject_register_signals`: before `g_signal_new`, call
  `g_signal_lookup(name, gtype)`. If non-zero, skip — but verify the
  signature still matches; warn if not (signature change on reload is a
  user error, not silently accept).
- `goi_gobject_register_properties`: same pattern with
  `g_object_class_find_property`. Mismatched pspec on reload — warn,
  keep existing.
- `Gtk.Template`: `set_template` is called once per GType. Reload skips
  if `cls.__goi_template_installed__` is already set. Template
  modifications (new child names, removed handlers) require restart;
  the doc warns about this as a known limit.

These are all small additions to the existing registration sites.

## Public API

```python
import goi

# Reload a module that defines GObject subclasses. All other behavior
# matches importlib.reload() — module globals are re-executed.
goi.reload_module(module)

# Optional: install a watchdog. Drives the same path on inotify events.
goi.watch_modules([mymodule], interval=0.5)
```

Implementation: `reload_module` calls `importlib.reload` after stashing
the live class-registry entries for each `__gtype_name__` the module owns.
After the module body re-runs, post-process: walk the new class objects,
trigger the instance-swap + vtable-restore pass per affected GType, then
emit a `goi:reloaded` signal so app code can re-run e.g. `app.lookup_action`
caches.

## Module-level state — lean on GApplication's lifecycle

Re-executing the module body re-runs top-level statements:

```python
app = Gtk.Application(application_id="org.example.App")
app.connect("activate", on_activate)
```

A naive reload that re-executes this builds a *new* Application while
the original is still alive — double-bound, leaking.

GApplication already has the right lifecycle for this: `startup` runs
once per process, `activate` runs for every "show the UI" event
(including remote-instance re-launches), `shutdown` runs once on quit.
The canonical GNOME app structure puts construction of the GApplication
in module-level code (or a one-shot `main()`), action installation in
`startup`, and window construction in `activate`. That structure maps
directly onto reload:

- **The GApplication instance survives reload.** It's tied to
  `startup`, which we don't re-fire.
- **Windows are rebuilt by re-firing `activate`.** After the module
  body has been re-executed (so `on_activate` now refers to the new
  function), `goi.reload_module` calls
  `app.activate()` to rebuild the window tree against the new code.

Concretely:

```python
goi.reload_module(my_app_module, app=my_app)
```

The reload pass:

1. Stash class-registry entries for the GTypes this module owns.
2. Disconnect tracked signal handlers from the old module (section 3).
3. Destroy windows belonging to `app`:
   `for w in list(app.get_windows()): w.destroy()`. (Skipping this is
   fine for genuinely idempotent activate handlers, but most apps
   build a window per activate; without the destroy you get two.)
4. `importlib.reload(module)` — body re-runs, `app = ...` reuses the
   passed-in singleton (helper below), new `on_activate` becomes the
   bound handler.
5. Swap instance `__class__`es and restore vfunc tables.
6. `GLib.idle_add(app.activate)` — fires `do_activate` on the new
   handler from a clean main-loop tick.

App authors who already structured their code the GNOME way (startup
for actions, activate for windows) get reload with zero refactoring.

### Fallback: `goi.module_singleton`

For code that doesn't use GApplication — standalone scripts, library
modules that hold module-level state — provide:

```python
app = goi.module_singleton(
    "app",
    lambda: Gtk.Application(application_id="org.example.App"),
)
```

Cache lives on the module object so the same call returns the
existing instance after reload. This is the escape hatch; the primary
path is GApplication.

## Out of scope (v1)

- **Adding/removing signals or properties between reloads.** Detected and
  warned, but the class keeps the originals. Restart for those.
- **Changing the `__gtype_name__`.** Treated as a new class, no link to
  the old GType — old instances stay on the dead class.
- **Cross-module GObject inheritance with reload.** If module A defines
  `Foo(GObject.Object)` and module B defines `Bar(A.Foo)`, reloading A
  has to invalidate B's class too. Detectable via the GType parent chain
  but not handled in v1 — document as restart-required.
- **C-defined GObjects.** Anything from `Gtk.Window` down stays as-is.
  Only Python subclasses participate in reload.

## Implementation order

1. **Wrappers-per-type index** (`Object-wrap.c`). Hash table + insert/remove
   in register/dealloc. ~40 lines. Verifiable in isolation via a unit
   test that constructs N wrappers and counts the index size.

2. **Instance-swap pass** (`reload.c`, new file). Given (gtype, new_class),
   walk the index, `Py_SET_TYPE`. Test: build a wrapper, swap the class,
   check `type(obj) is new_class` and method calls hit the new code.

3. **Vtable snapshot + restore** (`Object-vfunc.c`). Snapshot on first
   install, restore on reload-marker call. Test: install override A,
   restore, check vfunc dispatches to parent; install A then "reload" to
   B, check dispatches go to B.

4. **Signal-handler tracking** (`Object-connect.c`, `Template.py`).
   Per-module list of `(GWeakRef target, gulong handler_id)` populated
   on `obj.connect(...)`. Test: connect, reload, verify the old
   handler is disconnected and not invoked.

5. **Idempotent signal/prop registration** (signal/properties files).
   Lookup before register, warn on mismatch. Test: register `my-signal`
   twice, second is a no-op + warning.

6. **`goi.reload_module` Python entry** (`src/goi/reload.py`). Wraps
   `importlib.reload` with the stash → disconnect → window-destroy →
   re-exec → swap → re-activate choreography.

7. **`goi.module_singleton` helper** (`src/goi/reload.py`). Cache on the
   module object — fallback for non-GApplication code.

8. **Doc + sample**: a `tests/test_hot_reload.py` integration test that
   builds an `app.activate`-driven window, reloads its module, asserts
   the window's method dispatch picks up the new code AND that a stale
   signal handler from the pre-reload module is no longer firing.

Estimate: 3–4 days for the core (steps 1–6), another 1 for polish (7–8)
and bug-fixing on real reloads. Signal-handler tracking is the largest
of the new pieces because it has to cover the template path too.

## What this unlocks

Beyond the docviewer use case:

- **Edit-during-development**: GNOME-style apps could reload plugin modules
  without losing UI state. Quod Libet already does this for pure-Python
  plugins; the GObject limitation has been the obstacle to extending it.
- **REPL-driven UI building**: build a window, tweak the class, see the
  change. The "Smalltalk image" experience for GTK.
- **Cambalache / Workbench integration**: their preview-restart model
  could become preview-reload, much faster feedback loop.

The user-facing pitch is "edit, save, see — without losing where you
were." That's the thing PyGObject couldn't deliver and goi can.

## Risks

- **`Py_SET_TYPE` corner cases**. Subclasses-of-subclasses might have
  different `tp_dictoffset`. Need to verify the layout invariant holds
  across the goi heap-type builder and document if it doesn't.
- **Vtable snapshot leaks**. If a parent class itself gets unloaded
  (unlikely but possible in plugin scenarios), the snapshot dangles.
  Mitigation: snapshot live for the GType's lifetime, no reload across
  GType destruction (which doesn't happen in practice).
- **Free-threaded build interactions**. The instance-swap walk has to be
  GIL-held but also race-free against the class registry mutations.
  Existing class-registry lock already covers the registry side; the
  per-type wrapper index needs its own lock or to reuse the registry's.
- **GIL semantics during reload**. Module body re-execution can release
  the GIL on I/O. We don't want a concurrent thread to construct an
  instance of the half-rebuilt class. Either hold a reload mutex over the
  whole rebuild, or accept the race and document.

None of these are show-stoppers; all need explicit handling.
