# Clipboard

> Copy and paste, with the same content-provider model as drag and drop. Short chapter that builds directly on [Drag and drop](drag-and-drop.md).

## What this chapter covers

- The clipboard objects: `Gdk.Clipboard` and `Gdk.Display.get_clipboard()` (the regular one) vs `get_primary_clipboard()` (the X11/Wayland selection clipboard).
- Setting clipboard content: `set_content(Gdk.ContentProvider)`, simple `set_text` / `set_value` shortcuts.
- Reading clipboard content asynchronously: `read_text_async`, `read_value_async`, `read_async` for arbitrary content.
- Format negotiation and waiting for content from other apps.
- Patterns: copy-on-cut, large content (defer with a provider), images, custom MIME types.
- Wayland vs X11 differences (especially around the primary selection).

## What you'll be able to do

- Implement copy/paste in your app for text, images, and custom formats.
- Read what's currently on the clipboard without freezing the UI.

## Notes for the writer

- Keep this short; reuse `Gdk.ContentProvider` examples from the DnD chapter.
- Show one example with a custom format (e.g., copying a structured object as both text and a custom MIME type).
