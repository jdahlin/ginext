# Custom widgets

> When the built-in widgets don't fit, subclass `Gtk.Widget`. This chapter covers the lifecycle, layout protocol, snapshotting, and event handling for a widget you write from scratch.

## What this chapter covers

- When to write a custom widget vs composite-widget (template).
- The lifecycle: `init`, `realize`/`unrealize`, `map`/`unmap`, `dispose`.
- Layout protocol:
    - `measure(orientation, for_size) -> (min, nat, min_baseline, nat_baseline)`.
    - `size_allocate(width, height, baseline)`.
    - Children: allocating, walking, parenting.
- Snapshotting: `snapshot(snapshot)` — emit your render nodes.
- Event controllers attached in `init` (cleaner than overriding event signals).
- Adding properties, signals, CSS nodes, and accessibility properties to your widget.
- Sizing strategies: fixed size, content-driven, expand-fill.
- Animations: `Gtk.Widget.add_tick_callback` for per-frame work; `Adw.TimedAnimation`.
- Subclassing existing widgets vs subclassing `Gtk.Widget` directly.
- A worked example: a simple chart widget — measure, allocate, snapshot, expose data via properties.

## What you'll be able to do

- Write a custom widget that participates in the GTK layout system correctly.
- Emit render nodes for it.
- Expose it to Builder, Blueprint, and CSS.

## Notes for the writer

- This is one of the most-requested topics. Spend the time.
- The chart-widget worked example should be runnable; pull it from `examples/` or make it canonical here.
