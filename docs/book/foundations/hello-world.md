# Hello world

> A window with a button. Every line explained. The smallest program that exercises the full GTK lifecycle.

## What this chapter covers

- The 20-line program: `Gtk.Application` → activate signal → `Gtk.ApplicationWindow` → child widget → `present()`.
- Why `Gtk.Application` and not just `Gtk.Window`: single-instance, app ID, action map, lifecycle hooks.
- The main loop: who runs it, what it does, where the program "sleeps."
- Connecting a signal (`clicked`) and what closure capture looks like in Python.
- Running the program and reading the resulting window: title bar, default size, focus, close behavior.
- A short tour of what's *not* in this program but will appear soon: actions, headerbars, templates, async work.

## What you'll be able to do

- Run a GTK program from your terminal.
- Explain every line of it to a colleague.
- Recognize the lifecycle pattern (`activate` callback) you'll see in every subsequent chapter.

## Notes for the writer

- Keep the example small enough to hold in working memory. Resist adding "just one more widget."
- Show the program both as a plain `.py` script and as a function called from `__main__` — the latter is the form used everywhere else.
- Annotate the code with `# (1)`-style callouts; mkdocs-material renders these inline.
- End with "where to go next": layout, signals/properties, GtkApplication chapter.
