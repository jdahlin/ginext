# Accessibility

> Not optional. Required for GNOME Circle, required for Flathub quality, required to ship to humans. GTK4 makes basic a11y mostly automatic, but the details matter.

## What this chapter covers

- The model: GTK 4 has a built-in accessibility tree exposed via AT-SPI. You annotate widgets; ATs (Orca, Magnifier) consume.
- Accessibility properties: `accessible-role`, `accessible-name`, `accessible-description`, `accessible-label`, `accessible-controls`, `accessible-described-by`, `aria-*`-style relations.
- Setting accessibility from code, from `.ui`, from Blueprint.
- Labels and descriptions:
    - Buttons with only icons need a label.
    - Status messages need to be announced (`Gtk.Accessible.update_state(...)`).
    - Dynamic content updates (`AccessibleProperty.LIVE`).
- Focus management:
    - Visible focus on all interactive widgets.
    - Tab order, focus traps in dialogs.
    - Restoring focus after a dialog closes.
- Keyboard-only navigation: everything reachable, no mouse-only flows.
- Color contrast: never encode information in color alone.
- Reduced motion (`prefers-reduced-motion`): disable nonessential transitions when requested.
- Larger text scale.
- Testing:
    - Orca screen reader walkthrough.
    - The Accessibility Inspector (built into GTK; `GTK_DEBUG=interactive`).
    - High-contrast theme.
    - Keyboard-only smoke test.

## What you'll be able to do

- Annotate widgets so screen readers describe them correctly.
- Make every flow keyboard-reachable.
- Test your app with Orca before users have to.

## Notes for the writer

- This chapter must be substantive — the GNOME quality bar requires it.
- Include a checklist readers can paste into a PR template.
- Pair with the Orca tutorial as homework.
