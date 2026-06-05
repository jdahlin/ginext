# `ginext.extend` — User-Facing Extension API

## Purpose

`ginext.extend` is the user-facing runtime API for adding to or overriding symbols in any
loaded GI namespace. It is distinct from the internal compiled overlay system (see
`overlays.md`): compiled overlays are TOML→C, built into ginext, and run at zero Python
startup cost. `ginext.extend` is Python-level, runtime, and user-authored.

Inspired by Swift extensions and C# extension methods. The name `extend` signals the
operation rather than the mechanism.

---

## API

```python
@ginext.extend.add("Gtk")
def some_new_fn(widget, ...):
    ...

@ginext.extend.override("Gtk", "Widget")
class GtkWidget(BaseClass):
    def some_method(self):
        ...

@ginext.extend.override("GLib")
def idle_add(func, *args, priority=GLib.PRIORITY_DEFAULT_IDLE):
    ...
```

### `ginext.extend.add(namespace)`

Adds a new symbol to the namespace. `namespace` is a string. The decorated function or
class name becomes the attribute name on the namespace object.

Use when the symbol does not already exist in the typelib.

### `ginext.extend.override(namespace, class_name=None)`

Replaces an existing symbol. With one argument, replaces a namespace-level function or
object. With two arguments, merges the class body into the existing class.

For class overrides: the class body provides only the methods and properties being added or
replaced. The declared base (`BaseClass`) is a lightweight placeholder — ginext does **not**
rebuild the full `Gtk.Widget` MRO. The live class in the namespace already has its real
bases; the extension body is merged into it. This avoids the cost of constructing all
ancestor classes just to attach a few methods.

---

## Runtime Registration

Extensions can be registered at any point — before or after the target namespace is imported.

- **Namespace not yet loaded:** registration is queued. The extension is applied when the
  namespace is first opened (same apply path as compiled overlays).
- **Namespace already loaded:** the extension is applied immediately to the live namespace
  and class objects.

Both paths produce identical results. An extension registered before or after import behaves
the same at the call site.

---

## `add` vs `override` Distinction

| | `add` | `override` |
|---|---|---|
| Target exists in typelib | No | Yes |
| Tooling can warn on mismatch | If symbol appears | If symbol disappears |
| Semantics | New surface | Replacement |

The distinction is meaningful for library version upgrades: a future linter can warn if
`override` targets a symbol that no longer exists in a newer typelib version.

---

## Calling the Original

For `override` on a function, the original introspected callable should be accessible so
wrappers can delegate:

```python
@ginext.extend.override("GLib")
def idle_add(func, *args, priority=GLib.PRIORITY_DEFAULT_IDLE):
    # call the original GLib.idle_add_full underneath
    return ginext.extend.original("GLib", "idle_add")(func, *args, priority=priority)
```

The exact API for reaching the original is TBD. Options:
- `ginext.extend.original(namespace, name)` — explicit lookup
- Injected as a default argument — `def idle_add(func, *args, _original=None)`
- First argument to the decorator factory — `@ginext.extend.override("GLib", original=True)`

---

## Ecosystem Consistency

User-defined extensions create the same "dialect" risk as Ruby monkey-patching or Babel
transforms: two codebases using ginext may look different if they use different extensions.

Mitigations:

- Extensions are **visible at registration site** — a reader can find `ginext.extend` calls
  with a simple grep.
- ginext-shipped compiled overlays define the **canonical dialect**; user extensions are an
  explicit opt-in.
- Extensions registered in a module only take effect when that module is imported — the
  import graph makes them discoverable, similar to how Swift extensions require importing the
  module that defines them.
- Tooling can report active extensions on a namespace: `ginext.extend.list("Gtk")`.

---

## Motivating Use Cases

**String enum coercion** (instead of adding to the core marshal layer):

```python
@ginext.extend.override("Gio", "File")
def copy(self, destination, flags="none", ...):
    if isinstance(flags, str):
        flags = Gio.FileCopyFlags[flags.upper()]
    elif isinstance(flags, list):
        flags = functools.reduce(
            lambda a, b: a | Gio.FileCopyFlags[b.upper()],
            flags,
            Gio.FileCopyFlags.NONE,
        )
    return self._copy_original(destination, flags, ...)
```

**Adding missing convenience APIs:**

```python
@ginext.extend.add("Gtk")
def label(text: str, **kwargs) -> Gtk.Label:
    return Gtk.Label(label=text, **kwargs)
```

**Retroactive protocol conformance** (GListModel as a Python sequence):
Already shipped in ginext's compiled overlays; user extensions give the same power to
application code.

---

## Relationship to Compiled Overlays

| | Compiled overlays | `ginext.extend` |
|---|---|---|
| Author | ginext maintainers | Application/library authors |
| Format | TOML → C static data | Python decorators |
| Apply time | Namespace open (zero-cost) | Registration time or namespace open |
| Scope | ginext-internal ABI2 shims | User customisation |
| Override original | Via identifier redirect | Via `ginext.extend.original()` |

User extensions should not try to replicate what compiled overlays already do. If a
customisation is broadly useful, it belongs in ginext's compiled overlay layer, not in
every application's `ginext.extend` calls.
