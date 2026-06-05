# CSS styling

> GTK4 uses a CSS subset for styling. It's familiar but not identical to web CSS — no flexbox, no grid (in CSS — use containers), and a different set of selectors and properties.

## What this chapter covers

- The GTK CSS model: nodes, selectors, pseudo-classes, state.
- What's supported and what isn't (no `display`, no `position:absolute`, limited layout — layout is widgets, not CSS).
- Selectors: type, class, ID, descendant, child, `:hover`, `:focus`, `:active`, `:checked`, `:disabled`, `:dir(rtl)`.
- Common properties: colors, backgrounds (incl. gradients), borders, padding, margins, fonts, transitions.
- Named colors and theme integration (`@accent_color`, `@theme_fg_color`, …) — how to write CSS that respects the user's theme.
- Loading CSS:
    - `Gtk.CssProvider.load_from_path` / `_from_resource` / `_from_data`.
    - Provider priorities (`PRIORITY_APPLICATION`, `PRIORITY_USER`, …).
    - Scoping a provider to a widget vs the whole display.
- Style classes: `widget.add_css_class("suggested-action")`. The standard set provided by GTK and how to discover them with the inspector.
- Animations and transitions.
- Debugging styles with `GTK_DEBUG=interactive`.

## What you'll be able to do

- Style your widgets to match the platform or your brand.
- Respect light/dark themes automatically.
- Debug "why isn't my style applying?" with the inspector.

## Notes for the writer

- This chapter belongs in Part II because non-GNOME apps need it too; GNOME-specific CSS conventions get their own chapter in Part IV.
- Show a real example that styles a custom widget cleanly with state pseudo-classes.
- Warn against fighting the theme; show the named-color approach instead.
