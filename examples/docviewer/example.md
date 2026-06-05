# Hello, goi

This is a tiny markdown document with **runnable** snippets. Each
fenced block tagged `{goi:run}` becomes an editable example with an
inline preview rendered by `Casilda.Compositor`.

## A window

The simplest possible GTK4 program — open a window and show some text.
Edit the code and hit Run to see your changes.

```python {goi:run}
import goi as _gir
_gir.install_as_gi()
_gir.require_versions({"Gtk": "4.0"})

from gi.repository import Gtk

def on_activate(app):
    win = Gtk.ApplicationWindow(application=app, title="Hello")
    win.set_default_size(360, 200)
    win.set_child(Gtk.Label(label="Hello from goi!"))
    win.present()

app = Gtk.Application(application_id="org.goi.example.Hello")
app.connect("activate", on_activate)
app.run([])
```

## A button

Signals work the same as any other GTK app. Try changing the label or
the click handler.

```python {goi:run}
import goi as _gir
_gir.install_as_gi()
_gir.require_versions({"Gtk": "4.0"})

from gi.repository import Gtk

def on_activate(app):
    n = [0]
    btn = Gtk.Button(label="Click me")
    def on_click(_b):
        n[0] += 1
        btn.set_label(f"Clicked {n[0]}")
    btn.connect("clicked", on_click)

    win = Gtk.ApplicationWindow(application=app, title="Button")
    win.set_default_size(300, 160)
    win.set_child(btn)
    win.present()

app = Gtk.Application(application_id="org.goi.example.Button")
app.connect("activate", on_activate)
app.run([])
```

## A non-runnable block

Some blocks are just illustrations and shouldn't be runnable — leave
off the `{goi:run}` attribute and they render as plain code.

```python
# Just a snippet, not wired up.
def greet(name: str) -> str:
    return f"Hello, {name}"
```
