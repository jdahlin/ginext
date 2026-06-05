# Rust extensions (gtk-rs)

> You can write GObject types in Rust and expose them via GIR the same way you would in C — often with nicer ergonomics. This chapter is the survival kit.

## What this chapter covers

- The `gtk-rs` ecosystem in one paragraph: idiomatic Rust bindings to GTK and friends, with a macro-based way to declare GObject subclasses.
- `gobject-subclass`: the crate that lets you write `#[derive(ObjectSubclass)]` etc. — Rust's equivalent of `G_DECLARE_FINAL_TYPE`.
- Properties, signals, virtual methods in Rust.
- Building a `cdylib` and generating a `.goi` from it (mostly with the same `gnome.generate_gir` meson glue as C).
- Ownership at the FFI boundary: how Rust's borrow checker interacts with GObject's refcounted world (`glib::Object`, `WeakRef`).
- When Rust beats C here: safer parsers, faster work without bugs, better async story.
- When C is still simpler: very small wrappers; existing C codebases.
- A worked example: a Rust GObject type ported from the C example in the [C chapter](c-gobject-library.md).

## What you'll be able to do

- Decide between C and Rust for a new extension.
- Stand up a Rust-GObject project that produces a typelib goi can consume.

## Notes for the writer

- Be honest about the buildchain cost — adding Rust to a project is non-trivial.
- Cross-link to gtk-rs docs for current API; pin gtk-rs version when writing.
