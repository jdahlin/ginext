# Phosh and mobile

> Phosh is GNOME's mobile shell, running on Librem 5, PinePhone, and friends. libadwaita's adaptive widgets exist largely to support this; building a phone-friendly app is a real shipping target.

## What this chapter covers

- The hardware: small portrait screens, touch primary, on-screen keyboard, sometimes physical buttons.
- Mobile-first vs adaptive: design at narrow widths and grow up, not the other way.
- libadwaita primitives that earn their keep on Phosh:
    - `Adw.NavigationSplitView` collapsed mode.
    - `Adw.Dialog` as a bottom sheet.
    - `Adw.Clamp` for readable line lengths.
    - `Adw.Breakpoint` setters keyed on `max-width: 600sp`.
- Touch targets: minimum sizes, generous hit areas.
- On-screen keyboard: focus management, scroll-on-focus.
- The phone-app HIG: differences from desktop GNOME (more swiping, fewer headerbar items).
- Power and resources: aggressive about pausing background work.
- Testing on Phosh: GNOME Shell mobile mode, the Phosh "screen-size" emulation, real devices.
- Distribution: most Phosh apps ship on Flathub the same as desktop.

## What you'll be able to do

- Build an app that's usable on a phone, not just "scaled down."
- Test mobile flows without owning the hardware.

## Notes for the writer

- Cross-link heavily to [Adaptive UI and breakpoints](../gnome/adw-adaptive.md).
- Many readers won't ship to mobile but will benefit from designing adaptively; lead with that.
