# FreeType

> The font rasterizer under HarfBuzz, Pango, and Cairo. Even more invisible than HarfBuzz.

## What this chapter covers

- What FreeType is: a font loader and rasterizer. Decodes TTF, OTF, WOFF, more.
- When you might call FreeType directly:
    - Reading font metadata (family, style, OS/2 info) without rendering.
    - Implementing your own glyph cache.
    - Custom font rendering outside Cairo/Pango.
- The API tour: `FT_Library`, `FT_Face`, `FT_Load_Glyph`, `FT_Render_Glyph`.
- Hinting: byte-code interpreter, autohinting, when to disable.
- Subpixel rendering and LCD filters.
- Color fonts (COLR/CPAL, SVG-in-OT, sbix) — modern fonts have color glyphs.
- Variable fonts: axis values, named instances.

## When you'll come here

- You're writing rendering code that bypasses Pango/Cairo.
- You're building font-management UI.

## Notes for the writer

- The most niche chapter in the book. Keep it short; link to FreeType's own docs heavily.
