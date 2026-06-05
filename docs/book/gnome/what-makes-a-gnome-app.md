# What makes an app a GNOME app

> The HIG, the platform conventions, and the design philosophy that distinguishes "a GTK app" from "a GNOME app." Read this before writing a line of GNOME-specific code.

## What this chapter covers

- The GNOME Human Interface Guidelines: the document, what it covers, how to read it.
- Design philosophy in one page: opinionated defaults, fewer options, content-focused, accessible by default.
- The headerbar-centric layout (no menubar, no toolbar, optional primary menu).
- The "one window does one thing well" pattern; multi-window vs multi-page.
- Modal dialogs are rare; toasts and inline UI are preferred.
- Sandboxing as the norm — design assuming Flatpak.
- Visual hallmarks: large hit targets, generous padding, symbolic icons, light/dark, accent colors.
- What GNOME apps **don't** do: tray icons, splash screens, custom title bars (except via libadwaita patterns), settings-heavy UIs.
- Differences vs "just GTK" apps: settings UI conventions, naming, asset bundling, distribution.

## What you'll be able to do

- Recognize a GNOME app on sight and explain why.
- Make design decisions that align with the platform rather than fight it.
- Know when *not* to follow GNOME conventions (you're shipping cross-DE, etc.).

## Notes for the writer

- This is a philosophy chapter, not a code chapter. Screenshots of representative apps help more than snippets.
- Be direct about controversial conventions (no menubar, no tray); explain the reasoning rather than defending them.
- Forward-link to the libadwaita section as the toolkit that *implements* these conventions.
