# When to drop to native code

> Most reasons people write C extensions don't survive scrutiny. This chapter is a decision rubric.

## What this chapter covers

- The four common reasons people reach for C:
    1. **Performance** — usually fixable in Python first. Profile before rewriting.
    2. **Wrapping an existing C library** — almost always the right call, especially if it has GObject types.
    3. **Exposing your own reusable API to other languages** — write a GObject library; you get Python, JS, Vala, and Rust bindings for free.
    4. **OS APIs not exposed via GObject** — rare; usually a portal or GIO wrapper exists.
- The recommendation hierarchy:
    1. **GObject library in C/Rust + GIR** — best path, ecosystem-friendly.
    2. **Pygir overlay** — when the C library exists but its bindings need Pythonification.
    3. **Small CPython extension** — last resort, isolates you from the GObject ecosystem.
- When *not* to drop to native:
    - You haven't profiled.
    - The hotspot is I/O-bound.
    - The hotspot is Python-side data structures you can replace (dict → set, list → deque).
    - The hotspot is in a `bind` factory that runs once per visible row (fix the factory, not the language).
- A worked example of "we thought we needed C, we didn't."

## What you'll be able to do

- Pick the right approach honestly.
- Articulate the case for or against native code in a PR.

## Notes for the writer

- Short, opinionated chapter. The rest of Part VII is for the cases that survive this filter.
