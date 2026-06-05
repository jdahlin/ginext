# HarfBuzz

> The text shaper under Pango. Almost always invisible. The 0.1% of GTK app developers who need it should look here.

## What this chapter covers

- What HarfBuzz is and isn't: an OpenType shaper, *not* a layout engine. Pango calls it; you usually don't.
- When you might call HarfBuzz directly:
    - Building a custom text engine that doesn't use Pango (rare).
    - Inspecting OpenType features available in a font.
    - Pre-computing glyph runs for performance-critical text rendering.
- Buffer model: `hb_buffer_t`, adding text, shaping, reading glyphs.
- Features: enabling/disabling OpenType features per buffer.
- Scripts and languages: how HarfBuzz decides shaping rules.
- Font loading: from a TTF/OTF file, from a `FT_Face`.
- Cluster information: mapping glyphs back to characters.
- Performance characteristics: HarfBuzz is fast, but allocating a buffer per word is not.

## When you'll come here

- You are writing your own text widget that bypasses Pango.
- You need to introspect or debug font feature support.

## Notes for the writer

- Honest acknowledgement: most readers never touch HarfBuzz directly.
- One worked example: shape a string and print the resulting glyph cluster info.
