# GObject for Python developers

> GObject is the type system underneath everything in GTK. Understanding it is the single biggest unlock — without it, signals, properties, templates, and bindings feel like magic. This chapter demystifies it.

## What this chapter covers

- **The type system**: `GType`, `GObject.Object`, why GTK isn't "just classes." Single inheritance + interfaces (`GInterface`).
- **Object lifetime**: floating refs, sink, ref/unref, and what goi handles for you vs what you need to know.
- **Subclassing GObject from Python**: `class Foo(GObject.Object)`, the `__gtype_name__` convention, registration timing.
- **Properties**: declaring with `GObject.Property`, getters/setters, `notify::` signals, `bind_property`.
- **Signals**: emitting, connecting, default handlers, `g_signal_handler_block`. Why signals aren't just Python callables.
- **Interfaces**: implementing `Gio.ListModel`, `Gtk.Buildable`, etc. from Python.
- **GValue and boxing**: the bridge between dynamic and static types — usually invisible, occasionally not.
- **GError**: the GObject error convention and how goi maps it to Python exceptions.
- **GVariant**: serialization for DBus, actions, GSettings. The data type readers will see everywhere in later chapters.

## What you'll be able to do

- Read GTK documentation written for C and translate it to Python.
- Subclass any GObject type and expose properties and signals to other GObject code (CSS, templates, bindings).
- Diagnose "missing property" / "no such signal" errors from first principles.
- Use `GVariant` and `GError` without consulting the docs every time.

## Notes for the writer

- This is *the* prerequisite chapter for Parts II–IV. Invest in it.
- Tone: "Python with extra structure," not "C concepts in Python clothing."
- Show the same idea from both sides: a Python subclass *and* the equivalent C `G_DECLARE_FINAL_TYPE` block, so readers can map docs they find online.
- Cross-link forward to chapters that build on each concept (properties → bindings, signals → events, GVariant → actions/GSettings).
