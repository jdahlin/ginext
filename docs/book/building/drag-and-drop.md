# Drag and drop

> GTK4 rebuilt DnD around event controllers and `Gdk.ContentProvider`. Source and target are independent; either can be your widget or someone else's.

## What this chapter covers

- The model: a **source** offers content via a `Gdk.ContentProvider`; a **target** advertises accepted formats and receives the drop.
- `Gtk.DragSource` controller: building content providers, drag icons, drag begin/end.
- `Gtk.DropTarget` and `Gtk.DropTargetAsync`: type negotiation, `on-drop`, hover feedback.
- Content formats: `Gdk.ContentFormats`, MIME types, GType-based formats, files (`Gio.File`/`GFile`-list).
- Common scenarios:
    - Reordering items in a list.
    - Dragging files in from the file manager.
    - Dragging text or images between apps.
- Custom data types: serialization, when to use a content provider vs a callback.
- Visual feedback: drag cursors, drop indicators, highlight CSS classes.
- Inter-process DnD considerations on Wayland and X11.

## What you'll be able to do

- Make your widgets drag sources and drop targets.
- Accept files dropped from the file manager.
- Reorder list items by dragging.

## Notes for the writer

- Provide one tight example for each of the three "common scenarios" above — these cover 90% of real DnD use.
- Mention portals briefly for sandboxed apps.
