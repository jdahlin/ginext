# Symbolic icons

> Monochrome SVGs that recolor automatically to match the surrounding text. Used in buttons, menus, list rows — anywhere you'd normally use a small icon.

## What this chapter covers

- What makes a symbolic icon: single-color SVG, drawn at 16×16, named `*-symbolic.svg`.
- The freedesktop icon-naming spec: standard names (`document-open-symbolic`, `view-list-symbolic`, …) — using these gets you free theming.
- The Adwaita symbolic icon set: how to browse it, where the file names come from.
- Adding your own: design constraints (16×16 canvas, single color, no gradients, no shadows), where to install (`data/icons/hicolor/symbolic/apps/<name>-symbolic.svg`).
- Custom symbolic icons in GResource (`/<app-id>/icons/scalable/actions/...-symbolic.svg`) — when not to install system-wide.
- Recoloring: how GTK applies the current text color and CSS recoloring classes (`success`, `warning`, `error`, `accent`).
- High-contrast variants.
- Common mistakes: multi-color "symbolic" icons that don't recolor; 32×32 icons that look fuzzy in 16-px contexts.

## What you'll be able to do

- Use standard symbolic icons by name everywhere your app shows one.
- Author and ship your own symbolic icons that recolor correctly.

## Notes for the writer

- Show one example of the same icon recolored four ways (default, success, error, white-on-dark).
- The icon-naming-spec link is essential — readers will return to it constantly.
