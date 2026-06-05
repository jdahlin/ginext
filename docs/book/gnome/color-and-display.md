# Color management and display

> Color profiles, HiDPI, fractional scaling, multi-monitor — the details that separate "works for me" apps from polished ones.

## What this chapter covers

- HiDPI fundamentals: device pixel ratio, GTK's scale factor, when SVG icons help and when they don't.
- Fractional scaling on Wayland: what's supported, common pitfalls (blurry pixmaps, wrong sizes).
- Per-monitor scale changes: listening for monitor change signals.
- Multi-monitor: `Gdk.Display`, `Gdk.Monitor`, picking the right monitor for a new window.
- Color profiles via colord: querying display profile, color-managed rendering for photo apps.
- Theming for outdoor / sunlight / high-contrast — high-contrast mode integration.
- Dark mode: respecting `Adw.StyleManager` (cross-link).
- Cursors: theme-aware cursors, custom cursors.
- Accessibility tie-ins: reduced motion, larger text scale.

## What you'll be able to do

- Render correctly on HiDPI and fractional-scaled monitors.
- Detect monitor changes and respond.
- Use color profiles for color-critical apps.

## Notes for the writer

- This chapter ages — pin a year. Wayland fractional-scaling state changes every release.
- Cross-link to [Accessibility](accessibility.md) for the reduced-motion and high-contrast specifics.
