# Migration from Qt / PySide

> Qt is the closest mainstream parallel to GTK — same era, same problems, similar answers. This guide maps your Qt knowledge onto GTK + goi with minimal re-learning.

## Concept map

| Qt | GTK / goi |
| --- | --- |
| `QObject` | `GObject.Object` |
| signals / slots | GObject signals (`connect`, `emit`) |
| `Q_PROPERTY` | `GObject.Property` |
| `QApplication` | `Gtk.Application` |
| `QWidget` | `Gtk.Widget` |
| `QMainWindow` | `Gtk.ApplicationWindow` / `Adw.ApplicationWindow` |
| `QVBoxLayout` / `QHBoxLayout` | `Gtk.Box` (orientation) |
| `QGridLayout` | `Gtk.Grid` |
| QML | Blueprint / GtkBuilder `.ui` |
| QSS | GTK CSS |
| `QAbstractItemModel` | `Gio.ListModel` + factories |
| `QStandardItemModel` | `Gtk.StringList`, `Gio.ListStore` |
| `QSettings` | `GSettings` |
| `QThread` / `QtConcurrent` | `Gio.Task`, `GLib.Thread`, `Gio.AsyncResult` |
| `qApp->exec()` | `Gtk.Application.run()` |
| `QTimer` | `GLib.timeout_add` |
| `QFileDialog` | portal file chooser / `Gtk.FileDialog` |

## What this chapter covers

- The concept map, walked through with side-by-side code (Qt left, goi right).
- Where the parallels break: layouts are containers (not separate `QLayout` objects); models are list-only (no row/column hierarchy by default); signals are named strings, not symbols.
- Threading: differences in how the main loop interacts with worker threads (`GLib.idle_add` ≈ `QMetaObject::invokeMethod`).
- Property bindings: `GBinding` vs Qt 6 bindings.
- Models and views: porting `QAbstractItemModel` to `Gio.ListModel` + `Gtk.ColumnView`.
- QML → Blueprint: side-by-side comparison.

## Worked example

Port a small Qt Widgets app (e.g. a notes app with a list + editor) to goi, file by file.

## Notes for the writer

- Pin Qt 6.x and PySide6.
- Don't bash Qt; readers liked enough of it to ship apps in it.
- Highlight the few places GTK is materially nicer (CSS, async I/O, portals) and the few places Qt is (mature designer, charts/data viz, deeper Windows polish).
