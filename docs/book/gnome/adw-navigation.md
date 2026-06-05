# Navigation (NavigationView, Split)

> The modern GNOME navigation primitives: push/pop stack, split views, adaptive sidebars. Replaces older `Gtk.Stack`-with-buttons patterns for most apps.

## What this chapter covers

- `Adw.NavigationView` and `Adw.NavigationPage`: the push/pop stack with built-in headerbar handling.
- `Adw.NavigationSplitView`: master-detail with adaptive collapse on narrow widths.
- `Adw.OverlaySplitView`: drawer-style sidebar that overlays instead of pushing content.
- Combining: `OverlaySplitView` containing `NavigationView` is the canonical "sidebar + content" pattern.
- Programmatic navigation: `push`, `pop`, `pop_to_tag`, replacing the stack.
- Per-page headerbar customization.
- Animations and transitions.

## What you'll be able to do

- Build sidebar/content apps the modern GNOME way.
- Wire push/pop navigation without hand-rolling a stack.

## Notes for the writer

- One worked example: a settings app with categories on the left and content on the right that collapses on narrow widths.
- Cross-link to [Adaptive UI and breakpoints](adw-adaptive.md).
