# CSS for GNOME apps

> Most styling in a GNOME app should be standard libadwaita classes — but sometimes you need custom CSS. The trick is writing it so the theme keeps working.

## What this chapter covers

- The rule: reach for documented classes first; custom CSS is the last 10%.
- Named theme colors:
    - `@accent_color` / `@accent_bg_color` / `@accent_fg_color`.
    - `@window_bg_color`, `@view_bg_color`, `@card_bg_color`, `@headerbar_bg_color`.
    - `@warning_color`, `@error_color`, `@success_color`.
    - `@borders`, `@shade_color`.
- Why you must use these, not hard-coded hex.
- Light/dark friendly patterns: use named colors; use `@alpha()` helpers; let the theme pick contrast.
- High-contrast considerations.
- Scoping CSS: `CssProvider` attached to a single widget vs the whole display; provider priority and the user's theme.
- Loading CSS from a GResource (the canonical path).
- Working with the Adw style classes from custom CSS (extending, not overriding).
- Debugging with GtkInspector's CSS panel.

## What you'll be able to do

- Add custom styling that respects light/dark and accent.
- Avoid the trap of "looks fine in dark, broken in light."

## Notes for the writer

- The named-color table is the most-referenced part — keep it current.
- Pair with the GTK [CSS chapter](../building/css.md) which covers the language itself.
