# Cambalache (visual UI editor)

> A graphical editor for GTK `.ui` files. The successor to Glade for GTK4. Useful for designers, useful for fast iteration, optional for everyone else.

## What this chapter covers

- What Cambalache does well: drag-and-drop widget composition, property panels, live preview, multi-target support (GTK3 and GTK4 projects).
- What it doesn't do (yet): Blueprint round-trip, full Adw widget coverage in some versions, source diffing.
- Workflow patterns:
    - Designer authors `.ui` in Cambalache; developer wires up signals and templates.
    - Hot-reload preview while editing.
    - Export to `.ui` for committing into the source tree.
- Limits to be aware of: complex widgets that need code (custom drawing, dynamic content), state across templates.
- When to skip Cambalache: keyboard-only devs, simple windows, Blueprint-first projects.

## What you'll be able to do

- Use Cambalache to draft window layouts visually.
- Hand off `.ui` files from a designer to your codebase cleanly.

## Notes for the writer

- Short chapter; Cambalache is a tool, not a programming model.
- Cross-reference Blueprint and `.ui` chapters — Cambalache is one path among several.
