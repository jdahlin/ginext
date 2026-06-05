# Text view

> `Gtk.TextView` is GTK's editable multi-line text widget. It's powerful, has its own model/view split, and has surprising depth — undo, marks, tags, iterators. This chapter walks through it end to end.

## What this chapter covers

- The model: `Gtk.TextBuffer` (the text + tags + marks) vs `Gtk.TextView` (the visual).
- Iterators: `Gtk.TextIter`, why they invalidate, how to navigate.
- Marks: persistent positions that survive edits; insert and selection_bound.
- Tags and `Gtk.TextTagTable`: applying formatting (bold, color, link), tag priorities, shared tag tables.
- Inserting text, replacing ranges, getting selected text, walking words/lines.
- Undo/redo: `enable_undo`, history, custom undo actions.
- Anchors and embedded child widgets.
- Scrolling: pairing with `Gtk.ScrolledWindow`, scrolling to a mark.
- Search and replace patterns (forward/backward, case-insensitive, regex via Python).
- Spellcheck integration.
- Performance characteristics on large documents and what to avoid.
- Syntax highlighting via `GtkSourceView` (sister library, brief intro).

## What you'll be able to do

- Build a basic text editor.
- Apply and toggle styled regions (bold, links, code spans).
- Implement find/replace.
- Reason about cost on big documents.

## Notes for the writer

- This is reference-heavy; consider splitting tags vs basics if it gets too long.
- Pull a worked example from the `apps/pyedit` port (it lives in this repo).
- Flag `GtkSourceView` as the right answer for code editing; don't try to roll your own.
