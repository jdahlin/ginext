# App icons

> The full-color icon shown in the dock, app grid, and Software. GNOME has an opinionated style for these; following it is part of looking like a GNOME app.

## What this chapter covers

- The GNOME app-icon style: rounded square, soft gradient, simple silhouette, no text, design at 128×128.
- Inkscape: the official app-icon templates, where to find them, how to use them.
- Anatomy of an icon: foreground silhouette, background gradient, optional subtle inner elements.
- Scalability: design at 128 and check at 32, 48, 64 — pixel hinting matters.
- Where the file goes: `data/icons/hicolor/scalable/apps/<app-id>.svg`.
- The dev/nightly variant: a striped/colored treatment with a `.Devel` App ID, so users can tell builds apart.
- The full-color symbolic counterpart for places that need monochrome (rare).
- Meson install rules for icon directories and refreshing the icon cache.
- Testing: GNOME Shell, app grid, Software, KDE Plasma fallback.

## What you'll be able to do

- Produce an icon that looks like it belongs on GNOME.
- Ship it correctly so every surface picks it up.

## Notes for the writer

- This chapter benefits from images. Use the official Adwaita app-icon template screenshots.
- Acknowledge that icon design is a craft; recommend hiring a designer for "real" apps.
