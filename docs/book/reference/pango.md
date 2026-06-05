# Pango deep reference

> Beyond what's in [Pango (text layout)](../deeper/pango.md): the long tail of Pango's API for anyone building heavy text rendering.

## What this chapter covers

- Font maps and contexts: `Pango.FontMap`, `Pango.Context`, per-display fonts.
- Font description grammar: `"Cantarell Bold Italic 12"`, parsing, generating.
- Attributes inventory:
    - `weight`, `style`, `variant`, `stretch`.
    - `foreground`, `background`, `underline`, `strikethrough`, `overline`.
    - `letter_spacing`, `rise`, `scale`.
    - `font_features` (OpenType features), `gravity`, `gravity_hint`.
    - `language`.
- Glyphs and shaping: `Pango.GlyphString`, `pango_shape`, working below the layout API.
- BiDi: `Pango.Direction`, `Pango.BidiType`, embedding levels.
- Tab stops and decimal alignment.
- Custom rendering: subclassing `Pango.Renderer`.
- Layout iterators and per-run inspection.
- Pango font features (OpenType ligatures, small caps, stylistic sets).

## When you'll come here

- Implementing a code editor with rich text features.
- Building a typesetting tool, e-book reader, or PDF generator.
- Debugging "why is my custom widget rendering text wrong?"

## Notes for the writer

- This is reference, not tutorial. Tone: dense, complete, with examples for the surprising bits.
- Cross-link sections to the matching Pango C docs.
