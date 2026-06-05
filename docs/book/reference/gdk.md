# Gdk internals

> GTK sits on top of Gdk: displays, monitors, surfaces, devices, events, the clipboard, content formats. Most of Gdk is covered by other chapters; this one is the reference for the rest.

## What this chapter covers

- `Gdk.Display`: the connection to the windowing system; getting the default, listing monitors.
- `Gdk.Monitor`: geometry, scale factor, model/manufacturer, refresh rate.
- `Gdk.Surface`: the underlying drawable; usually managed by GTK for you.
- `Gdk.Device` and `Gdk.Seat`: input devices, pointers, keyboards, touchscreens.
- `Gdk.Cursor`: built-in cursors (`text`, `pointer`, `wait`, `crosshair`, …) and custom cursors from textures.
- `Gdk.RGBA` and color parsing.
- `Gdk.Texture` and `Gdk.Paintable`: GPU-friendly image handles; the modern way to display images.
- `Gdk.Memory*Format` and frame-level color/alpha.
- `Gdk.ContentFormats`, `Gdk.ContentProvider`, `Gdk.ContentSerializer` / `Deserializer` (covered in [Drag and drop](../building/drag-and-drop.md) and [Clipboard](../building/clipboard.md)).
- Wayland vs X11 differences exposed at the Gdk level (most apps shouldn't care).

## When you'll come here

- Picking a monitor for a new window.
- Setting a custom cursor.
- Implementing `Gdk.Paintable` for a custom image type.
- Diagnosing input-device weirdness.

## Notes for the writer

- Reference flavored; minimal narrative.
- The `Gdk.Paintable` interface deserves its own section — many readers will need it for animated content.
