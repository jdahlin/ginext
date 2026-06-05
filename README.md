# ginext

Fast, lazy, JIT-compiled [GObject-introspection](https://gi.readthedocs.io/)
bindings for free-threaded Python.

ginext lets you call GObject-based libraries — GLib, GIO, GTK, GStreamer,
libsoup and more — directly from Python, reading their introspection typelibs at
runtime and JIT-compiling the call paths. It is built for the free-threaded
(no-GIL) CPython 3.14+ runtime.

```python
from ginext import Gtk

app = Gtk.Application(application_id="org.example.Hello")
```

## Install

```sh
pip install gi                # core (imports as `ginext`)
pip install gi[gtk]           # + GTK/Gdk/Pango/Gsk overlay
pip install gi[gio]           # + GIO overlay
pip install gi[gst]           # + GStreamer overlay
pip install gi[all]           # all overlays
```

The distribution is named `gi` on PyPI; the importable package is `ginext`
(`from ginext import Gtk`).

The core links against GLib / GObject / girepository-2.0 (≥ 2.80). On Linux these
come from your distribution; the overlay packages add Pythonic namespace overlays
and ship as pure-Python wheels. Cross-platform wheels that bundle the GTK /
GStreamer runtime are on the roadmap.

## Packages

| Package            | Contents                                   |
| ------------------ | ------------------------------------------ |
| `gi`               | Native core + GLib/GObject/GIRepository    |
| `ginext-gio`       | GIO / GioUnix overlay                       |
| `ginext-gtk`       | GTK / Gdk / Pango / Gsk overlay            |
| `ginext-gst`       | GStreamer overlay                          |
| `ginext-libsoup`   | libsoup overlay                            |
| `ginext-gi-compat` | PyGObject `gi.repository` compatibility    |

## License

LGPL-2.1-or-later. See [LICENSE](LICENSE).
