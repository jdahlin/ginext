# Writing a GObject library in C

> The recommended path: write a normal GObject library in C, generate a `.goi` and `.typelib`, and goi picks it up automatically. No binding code, no stubs, no glue.

## What this chapter covers

- The minimum viable GObject library:
    - `meson.build` with `gnome.generate_gir()`.
    - A `.h` and `.c` for a simple type using `G_DECLARE_FINAL_TYPE` / `G_DEFINE_FINAL_TYPE`.
    - Installation paths for the library, headers, GIR, and typelib.
- Type declarations:
    - `G_DECLARE_FINAL_TYPE` vs `G_DECLARE_DERIVABLE_TYPE`.
    - Class init, instance init, dispose, finalize.
    - Adding interfaces (`G_IMPLEMENT_INTERFACE`).
- Properties:
    - `g_object_class_install_properties` with `GParamSpec` array.
    - Get/set property dispatch via `g_object_class->set_property`/`get_property`.
    - Property flags (READWRITE, CONSTRUCT_ONLY, STATIC_STRINGS, EXPLICIT_NOTIFY).
- Signals:
    - `g_signal_new` with appropriate marshallers.
    - Default handlers, accumulators.
- Virtual methods (for derivable types).
- Building the typelib in meson:
    - `gnome.generate_gir(...)` with `sources`, `nsversion`, `namespace`, `dependencies`, `includes`.
- Consuming from goi:
    - Installing the typelib into `XDG_DATA_DIRS` (system) or shipping with your app.
    - `from goi.repository import YourNamespace`.
- A worked example: a `MyMath.Vec2` type with x/y properties and a `dot` method, used from Python.

## What you'll be able to do

- Write a small GObject library in C and call it from goi.
- Set up meson so `make install` puts the typelib where goi can find it.

## Notes for the writer

- This is the most important chapter in Part VII. Spend the time.
- Annotated `.c`/`.h` listing + the `meson.build` is the centerpiece artifact.
- Cross-link forward to [Annotations](annotations.md), which is where most bugs happen.
