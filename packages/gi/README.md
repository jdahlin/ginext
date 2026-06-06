# gi

Meta-package for [ginext](https://github.com/jdahlin/ginext) — fast, lazy,
JIT-compiled GObject-introspection bindings for free-threaded Python.

```sh
pip install gi          # core (import as `ginext`)
pip install gi[gtk]     # + GTK/Gdk/Pango/Gsk
pip install gi[all]     # all overlays
```

`pip install gi` installs `ginext-core`; the code imports as `ginext`
(`from ginext import Gtk`). This distribution ships no `gi` module and does not
conflict with PyGObject.
