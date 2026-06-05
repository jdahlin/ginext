# Part VII — Extending goi

The goi killer feature: you almost never write binding code. If you need C/Rust for performance or to expose a system API, the right path is to write a normal **GObject library** with introspection metadata — goi picks it up automatically. This Part walks through that path, plus the alternatives.

## Chapters

1. [When to drop to native code](when.md)
2. [Writing a GObject library in C](c-gobject-library.md)
3. [Introspection annotations](annotations.md)
4. [Async functions in C](c-async.md)
5. [Pygir overlays](overlays.md)
6. [Rust extensions (gtk-rs)](rust.md)
7. [FFI pitfalls and lifetimes](pitfalls.md)
