# Testing PyGObject Compatibility

PyGObject compatibility should be tested as an executable contract, not only by
copying upstream tests. Upstream tests are useful, but real applications also
depend on undocumented call shapes, overlay conveniences, signal lifetime rules,
template binding behavior, and UI wiring conventions.

The most useful model is to treat real PyGObject as an oracle: run the same
small scenario against PyGObject and against goi, capture normalized structured
output, and compare the two.

## Differential Oracle

Each compatibility case should be able to run under two backends:

- `pygobject`: plain `import gi`
- `goi`: `import goi; goi.install_as_gi(); import gi`

Run each case in a fresh subprocess so module state, loaded typelibs, required
versions, signal registrations, and GObject type registrations cannot leak
between backends.

The subprocess should print JSON rather than human-formatted text. Useful fields
include:

- returned value shape
- exception type and message
- warnings
- selected `dir()` or attribute presence
- `type`, `__module__`, MRO, and class identity shape
- signal/event logs
- widget-tree snapshots
- final app state

Known intentional differences should live in a small manifest, for example
`tests/compat/known_differences.toml`, so compatibility debt is explicit and
reviewable.

## Widget-Tree Page Tests

A Stoq-style page test that dumps the widget tree is a strong static verification
layer. It catches many failures before any scripted interaction runs:

- widget classes
- object names and CSS classes
- visibility and sensitivity
- parent-child structure
- key properties
- template children bound correctly
- resources loaded correctly
- action names and accelerators
- model item counts for list widgets

For goi, this directly exercises template loading, builder construction,
property marshalling, enum and flag conversion, resources, overlays, and
namespace/version resolution.

The tree dump should be normalized so irrelevant differences do not dominate:

- omit object addresses and unstable IDs
- sort unordered collections
- print enum and flag values in a stable form
- include only properties that matter for the page contract
- keep an allowlist for known backend differences

## Signals And Interactivity

The widget tree only proves that the UI was constructed. Compatibility also
needs signal wiring and interaction behavior.

Capture an event log while driving the page:

```text
clicked save_button
signal Gtk.Button::clicked args=[Button]
handler save_clicked returned None
notify::sensitive on save_button old=True new=False
action app.save activated parameter=None
```

The event log should cover:

- `connect`, `connect_after`, `disconnect`, and `handler_block`
- callback argument shape
- callback return value marshalling
- detailed signals such as `notify::property-name`
- default handlers and overridden vfunc paths
- builder/template callback lookup
- action activation
- property notifications
- object lifetime across signal connections

For deterministic tests, prefer direct signal emission and action activation
over full input automation:

- call `button.emit("clicked")`
- call `action.activate(parameter)`
- mutate model state directly
- spin the main loop until idle work drains
- dump the widget tree and event log again

Use real pointer and keyboard input for a smaller set of end-to-end smoke tests
where GTK's input machinery itself is part of the contract.

## Purpose-Built Signal Probes

Add small oracle probes for signal behavior that is easy to regress:

- `connect` calls handlers with PyGObject-shaped arguments.
- `connect_after` ordering matches PyGObject.
- `handler_block` suppresses exactly the expected emissions.
- `disconnect` removes exactly one handler.
- `emit` return values are marshalled correctly.
- detailed signals such as `notify::foo` work.
- builder/template callbacks bind to methods with the same accepted signatures
  as PyGObject.
- callbacks stay alive for as long as PyGObject would keep them alive.
- callbacks are released when PyGObject would release them.

Signal compatibility is not just whether the callback ran. It is whether the
argument list, user data shape, return conversion, handler ordering, and closure
lifetime match PyGObject closely enough for existing applications.

## Generated GIR Probes

Manual tests should be complemented by GIR-driven generated probes. The existing
coverage tooling can grow from "was this function called?" into shape coverage
by annotation class:

- primitive `in`, `out`, and `inout` arguments
- nullable/defaultable arguments
- arrays and length parameters
- `transfer none`, `transfer container`, and `transfer full`
- callbacks and closures
- boxed structs, unions, and fields
- GObject constructors, properties, and signals
- async/finish pairs

The goal is broad shape coverage, not deep semantic assertions for every symbol.
These probes should answer: "PyGObject accepts this call shape; does goi accept
it and return the same kind of result?"

## Real-App Smoke Tests

Real applications catch compatibility requirements that unit tests miss. The
Makefile already contains useful targets such as Drawing, Showtime, GNOME Music,
Cambalache, Quod Libet, pyedit, and web-browser.

For each app, define a minimal scripted smoke path:

- launch under goi as `gi`
- wait for the first window/page to settle
- dump the widget tree
- activate a small number of actions or signals
- dump the widget tree and event log again
- exit cleanly

Where practical, run the same smoke path under PyGObject and compare normalized
output. Where that is too expensive or environment-sensitive, keep the goi smoke
test as a regression guard and reduce failures into smaller oracle probes.

## Recommended Test Shape

A compatibility page test should produce three artifacts per backend:

- `initial_tree.json`
- `events.json`
- `final_tree.json`

The comparison should be strict by default and relaxed only through explicit
normalizers or known-difference entries.

This gives a useful split:

- widget-tree snapshots verify static UI construction
- event logs verify signal wiring and interaction flow
- final snapshots verify resulting state

Together, those cover much more of PyGObject compatibility than copied tests
alone.
