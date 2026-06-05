# Style classes and AdwStyleManager

> libadwaita ships a curated set of CSS style classes (`.suggested-action`, `.destructive-action`, `.pill`, `.flat`, `.card`, …) and a style manager that handles light/dark, accent colors, and high contrast.

## What this chapter covers

- Style classes vs hand-written CSS: prefer the named class.
- The standard set:
    - Buttons: `suggested-action`, `destructive-action`, `flat`, `pill`, `circular`, `osd`.
    - Containers: `card`, `boxed-list`, `boxed-list-separate`, `toolbar`.
    - Text: `title-1`..`title-4`, `heading`, `body`, `caption`, `dim-label`, `numeric`.
    - States: `success`, `warning`, `error`, `accent`.
- `Adw.StyleManager`:
    - Color scheme: `default`, `force-light`, `prefer-light`, `force-dark`, `prefer-dark`.
    - Following the system color scheme by default.
    - Reading the current accent color (named accents in newer libadwaita).
    - High-contrast mode.
- Reacting to scheme changes (refreshing custom-drawn widgets, regenerating icons).
- When to write your own CSS instead of using classes, and how to play nice with the theme.

## What you'll be able to do

- Style your app primarily through documented classes.
- Honor the system color scheme and high-contrast preference.
- Recolor custom-drawn elements when the scheme changes.

## Notes for the writer

- A cheat-sheet table of every standard style class with a one-line "use this when" is the most-referenced part of this chapter.
- Cross-link to [CSS for GNOME apps](css.md) for the custom-CSS path.
