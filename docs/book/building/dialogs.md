# Dialogs

> Asking the user a question, showing an alert, picking a file or color. GTK4 modernized this area significantly — async APIs, no more "run the dialog and block."

## What this chapter covers

- The shift in GTK4: no more `dialog.run()`; everything is async.
- `Gtk.AlertDialog` (replaces `Gtk.MessageDialog`): buttons, default, cancel, async `choose()`.
- `Gtk.FileDialog` (replaces `Gtk.FileChooserDialog`): open, save, select folder, filters; portal vs native.
- `Gtk.ColorDialog`, `Gtk.FontDialog`.
- `Gtk.PrintDialog` and printing basics.
- Custom dialogs: a window with a transient parent and modal mode.
- Patterns: blocking-feeling code with `await`, or callback style.
- Error reporting dialogs and when not to use one (toasts and banners can be better — forward link to libadwaita).

## What you'll be able to do

- Show alerts and choices without freezing the UI.
- Open and save files using the GTK4 async API.
- Build your own modal dialogs from a window.

## Notes for the writer

- This chapter is where async-vs-callback patterns first really bite. Show both.
- For file dialogs, mention the portal version arrives transparently inside Flatpak.
- Forward-link to `Adw.AlertDialog`, `Adw.MessageDialog`, `Adw.PreferencesDialog`, `AdwToast`, `AdwBanner` (all in Part IV).
