"""pyedit — a small gnome-text-editor-shaped showcase for goi.

Demonstrates: Adw.Application, AdwApplicationWindow, AdwTabView, AdwHeaderBar,
AdwToastOverlay, AdwPreferencesDialog, GtkSource.View / GtkSource.Buffer
(line numbers, syntax highlighting, search context, style schemes),
Gtk.Template (resource_path / filename), Gtk.Builder menus, Gio.Settings-style
JSON persistence, Gio.SimpleAction wiring, GtkSearchBar.

Not production: error handling is loose, encoding is utf-8, no plugins.
The intent is to exercise as much of goi's GIR coverage as one app can.
"""
