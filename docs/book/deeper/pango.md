# Pango (text layout)

> The text-shaping and -layout library underneath every label, every button, every text view. You rarely call it directly — but knowing the API helps when you need to render text in a custom widget or generate text-heavy graphics.

## What this chapter covers

- The pipeline: input text + attributes → font selection → shaping (via HarfBuzz) → layout → rendering.
- `Pango.Layout`: the workhorse. Setting text, font description, alignment, wrap mode, ellipsize.
- `Pango.AttrList` and per-character attributes: weight, style, foreground, underline, links.
- Pango markup: a small HTML-ish subset (`<b>`, `<i>`, `<u>`, `<span foreground='red'>`); when to use and when not.
- Coordinates: Pango units (1 unit = 1/`PANGO_SCALE` pixels). The constant gotcha.
- Measuring text: `get_size`, `get_pixel_extents`.
- Drawing: `pango_cairo_show_layout` from inside a Cairo context; `Gtk.Snapshot.append_layout` for Gsk integration.
- Rendering tabs, justification, BiDi (right-to-left).
- Font selection: `Pango.FontDescription`, font maps, fallback.
- When `Gtk.Label` is enough: most of the time. Only reach for Pango directly when you're drawing your own surface.

## What you'll be able to do

- Render text in custom widgets with proper layout.
- Apply per-character styling without subclassing.

## Notes for the writer

- Forward-link to the [Pango reference](../reference/pango.md) for the long tail.
- Pango markup is widely used — make sure readers come away comfortable with it even if they never call Pango directly.
