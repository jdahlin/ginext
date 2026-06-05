# Adaptive UI and breakpoints

> The same app on a 27-inch monitor and a 5-inch phone screen. libadwaita's breakpoints make this reasonable.

## What this chapter covers

- The mental model: declare *breakpoints* with width/height conditions; the system applies *setters* (property changes) when the condition matches.
- `Adw.Breakpoint`: condition syntax (`max-width:`, `min-height:`, combinations).
- `Adw.BreakpointBin`: container that switches its child layout based on breakpoint.
- Setters: changing widget properties when a breakpoint matches (e.g., `collapsed: true` on a split view).
- `Adw.Clamp` / `Adw.ClampScrollable` / `Adw.ClampLayout`: max-width content centering — the workhorse for readable layouts.
- Common adaptive patterns:
    - Split view that collapses to navigation on narrow.
    - Headerbar that switches from inline tabs to a dropdown.
    - Forms that go from two columns to one.
- Testing on different sizes without rebooting into Phosh.
- Phosh and mobile-first considerations (forward link to Part V).

## What you'll be able to do

- Design layouts that look right at any reasonable window size.
- Use Clamp to keep readable content from sprawling on wide windows.

## Notes for the writer

- This is what distinguishes GNOME apps from "GTK apps that happen to use Adw." Spend the time.
- Include screenshots at multiple widths of the same window.
