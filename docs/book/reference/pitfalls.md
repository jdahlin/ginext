# Pitfalls cheatsheet

> A condensed lookup of the bugs that bite repeatedly. Cross-references the per-topic pitfall sections elsewhere.

## What this chapter covers

A symptom → cause → fix table covering the most common bug categories. Each row has a one-line symptom and a link to the prose chapter that explains it in depth.

Headings include (each with a small table):

- **Layout**
    - "Widget invisible" → not added, not visible, parent allocated 0.
    - "Widget too small / too big" → expand vs align vs request mismatches.
    - "Text clipped" → ellipsize, label vs box constraints.
- **Signals & callbacks**
    - "Handler not firing" → wrong object, wrong signal name, signal blocked, handler returned `True`.
    - "Handler fires twice" → connected twice; subclass re-emission.
    - "Callback errors silently swallowed" → exception in Python callback eaten by GObject.
- **Properties & bindings**
    - "Property not bound" → missing notify flag, wrong source/target spec.
    - "Property change not reflected in UI" → bind direction, sync_create.
- **Actions**
    - "Action greyed out" → scope mismatch (`app.` vs `win.`).
    - "Action does nothing" → parameter type vs target type.
- **CSS**
    - "Style not applying" → provider scope, priority, theme overriding.
- **Async / I/O**
    - "Main loop frozen" → sync call on main loop.
    - "`await` returns wrong type" → wrong `_finish` signature, transfer.
- **Templates**
    - "Template child is None" → forgot `Gtk.Template.Child()`, wrong ID.
    - "Signal handler not connected" → missing `Gtk.Template.Callback`.
- **GResource**
    - "Resource not found" → wrong path, not registered, wrong gresource bundle.
- **GSettings**
    - "Schema not found" → schemas not compiled, `XDG_DATA_DIRS` mismatch.
- **FFI / GObject**
    - "Crash calling C method" → transfer/nullable/array-length annotation.

## Notes for the writer

- This is a *flat lookup*, not a tutorial. Optimize for scannability.
- Every row should link to a section in the book that explains it properly.
