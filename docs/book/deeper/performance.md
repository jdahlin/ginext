# Performance and profiling

> Where goi apps get slow and how to find out. The combined Python + C-extension stack means you sometimes need two profilers.

## What this chapter covers

- The main-loop discipline: never block on it. The cardinal sin and how to detect it.
- Frame budget: 16.6 ms for 60 fps. What fits and what doesn't.
- Python-side profiling:
    - `py-spy` (sampling, no instrumentation, works on live processes).
    - `cProfile` for deterministic hotspots.
    - Memory: `tracemalloc`, `pympler`.
- C-side profiling:
    - `sysprof` — the GNOME profiler. System-wide, low overhead, captures GTK's own marks.
    - `perf` for the brave.
- GTK-specific:
    - `GTK_DEBUG=interactive` for the inspector.
    - The inspector's "Recorder" tab for frame-by-frame analysis.
    - `GSK_DEBUG=renderer` to see which renderer is active.
    - `G_MESSAGES_DEBUG=GLib-GObject` and friends to see GObject churn.
- Common hotspots in goi apps:
    - Python <-> GObject crossings in hot loops.
    - Cairo paths rebuilt every frame instead of cached.
    - Inefficient `bind` callbacks on list factories.
    - Synchronous I/O on the main loop.
- Bench-driven optimization: write a benchmark before chasing.
- When to drop to C/Rust: when profiling shows Python-side dominates and there's no algorithmic fix.

## What you'll be able to do

- Identify whether your slow code is in Python, in GObject calls, or in rendering.
- Use sysprof and py-spy together to localize.
- Make principled decisions about rewriting hot paths in native code.

## Notes for the writer

- This chapter underwrites the [Extending goi](../extending/index.md) Part — readers reach for C *after* they have a profile.
