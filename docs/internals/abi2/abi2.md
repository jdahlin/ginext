# ABI2 Native Surface

ABI2 is the Python-native `goi` surface. It should expose GObject methods,
properties, signals, and async operations without making users reason about
GObject ownership, closure lifetime, or `_async` / `_finish` pairing for common
application code.

The main lesson for ABI2 is that many GTK, GIO, and GStreamer APIs become much
clearer when the binding exposes the familiar Python abstraction, not just the
mechanical GIR name. GIR still defines the callable inventory and native
semantics, but ABI2 should choose Python concepts such as context managers,
async iterators, path-like objects, descriptors, and result records when those
concepts are a tighter fit for users.

This directory splits the ABI2 design into focused documents:

- [Shared Namespace](shared-namespace.md): deterministic attribute lookup for
  methods, properties, and signals sharing one Python namespace.
- [Methods](methods.md): method descriptors, native wrapping boundaries,
  `MethodSignal`, and async-method policy.
- [Signals](signals.md): native signal objects, owner-aware connections,
  optional signal arguments, Python-defined signals, and notify.
- [Binding](binding.md): Python-native `GBinding` helpers for property
  descriptors, named options, transform callbacks, and handler-like unbind.
- [Errors](internals/abi2/errors.md): `GError` domain/code preservation, generated exception
  classes, builtin-compatible mappings, and async cancellation.
- [Gio.File](gio-file.md): Python-native file construction, async open,
  pathlib-inspired helpers, and GIO-specific caveats.
- [Prototype Plan](prototype.md): staged implementation plan for
  `_internal_invoke()`, hidden GIR methods, event-loop integration,
  `Gio.File`, `Gio.open`, awaitable methods, and exceptions.
- [Unresolved](unresolved.md): remaining design areas from the local
  GitLab/Discourse issue corpus, including closure ownership, async policy,
  subclassing, templates, expressions, and error integration.
- [Async Inventory](async.md): generated inventory of installed async GIR
  callables in GLib, GObject, Gio, Gtk, and Gst when available.
- [Conflict Inventory](conflicts.md): generated inventory of installed GIR name
  conflicts relevant to the shared namespace policy.

## Design Constraints

- Prefer a familiar Python abstraction when it preserves the underlying GObject
  semantics better than a direct C-name translation. Examples include
  `async with file.open(...)`, `async for child in file.iterdir()`,
  `MethodSignal`, and result records for multi-return finish functions.
- Do not add Pythonic aliases casually. ABI2 should choose one native spelling
  per concept, keep GIR/PyGObject spellings on the compatibility surface, and
  document any abstraction whose behavior differs from a direct wrapper.
- ABI2 wrappers may use GIR callables that are hidden from normal native
  attribute lookup. This is appropriate when exposing the low-level callable
  would create a competing public API for the same concept.
- A name must never silently prefer a method over a property, a property over a
  signal, or a signal over a method.
- Pure method/signal conflicts use one callable/connectable `MethodSignal`
  object at the short spelling.
- If a property participates in a conflict, property access remains a plain
  value and conflicted members use explicit escaped spellings.
- Signal connections on the native surface are owner-aware by default. Bound
  methods infer the owner; unowned callbacks are accepted with a
  `ginext.UnownedSignalHandlerWarning`; lambdas that close over more than one
  `GObject` raise `TypeError` because the inference is ambiguous.
- For operations with an explicit ABI2 async plan, the natural short method name
  is awaitable by default and the blocking operation uses an explicit `_sync()`
  suffix.
- Awaitable async wrappers require a call plan for finish pairing,
  cancellation, result shaping, and error propagation. Do not promote an
  operation to default-async from naming alone.
- Raised `GError` values keep domain, code, and message. ABI2 may use Python
  builtin-compatible exception bases only for codes with a clear semantic
  match, while preserving `except GLib.Error` as the catch-all.