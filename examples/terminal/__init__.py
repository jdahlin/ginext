"""terminal — a tabbed terminal showcase for goi.

Demonstrates: Adw.Application, AdwApplicationWindow, AdwTabView, AdwHeaderBar,
AdwToastOverlay, AdwPreferencesWindow, Vte.Terminal, Gtk.Template, Gio.SimpleAction.

A small gnome-terminal/Tilix-shaped surface: every tab is a Vte.Terminal spawned
into the user's $SHELL, with JSON-backed preferences (font, palette, scrollback,
opacity, cursor shape, bell).
"""
