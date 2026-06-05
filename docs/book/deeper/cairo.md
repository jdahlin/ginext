# Cairo (custom drawing)

> Cairo is GTK's 2D drawing library: paths, fills, strokes, patterns, text. Use it for charts, custom widgets, image manipulation, and PDF/SVG export.

## What this chapter covers

- The Cairo model: a context drawing onto a surface; immediate mode with a state stack.
- Surfaces: image, PDF, SVG, recording.
- Paths: `move_to`, `line_to`, `curve_to`, `arc`, `close_path`.
- Painting: `set_source_rgba`, `fill`, `stroke`, `paint`, `fill_preserve`.
- Patterns: solid colors, linear/radial gradients, image patterns, mesh gradients.
- Transformations: `translate`, `scale`, `rotate`, `transform`, `save`/`restore`.
- Text the Cairo way (basic) vs Pango (preferred): when to use which.
- Clipping and masks.
- Drawing inside a `Gtk.DrawingArea`: setting a draw function, getting a `cairo.Context`, redrawing on demand.
- Exporting: PDF, SVG, PNG.
- Performance: avoid path-heavy redraws; cache surfaces; understand when GTK4 uses GPU vs CPU paths.

## What you'll be able to do

- Render charts, custom widgets, and arbitrary 2D graphics.
- Export drawings to PDF/SVG/PNG.
- Reason about Cairo performance.

## Notes for the writer

- Substantial chapter. Lean on visual examples.
- Note that GTK4 itself uses Gsk (next chapter); Cairo is mainly for *your* drawing code, exported via `Gtk.Snapshot.append_cairo`.
