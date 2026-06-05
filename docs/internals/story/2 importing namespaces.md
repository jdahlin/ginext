# Importing Namespaces

`ginext` should make the ABI2 namespace the default surface:

```pycon
>>> import ginext
>>> from ginext import GLib, Gio, GObject
>>> GLib.__ginext_abi__
'native-v2'
```

There should be no separate "native mode" for normal users to discover. If
they imported from `ginext`, they are using ABI2.

## Version Selection

Version selection should happen before namespace import:

```pycon
>>> import ginext
>>> ginext.require_version("Gtk", "4.0")
>>> from ginext import Gtk
>>> Gtk.__version__
'4.0'
```

For namespaces with one obvious version in a process, unsuffixed imports should
be enough:

```python
from ginext import Gio
```

For documentation, generated stubs, and ambiguous installations, suffixed
modules can remain useful:

```python
from ginext import Gio2
from ginext import Gtk4
```

## Runtime Contract

Namespace objects should be cached by `(name, version)` and separated from any
compatibility namespace cache. A native class from `ginext.Gio` should not be
the same Python object as a compatibility class from `gi.repository.Gio`.

```pycon
>>> from ginext import Gio
>>> file = Gio.File("/tmp/demo.txt")
>>> file.__ginext_abi__
'native-v2'
```

## Implementation Notes

- Keep namespace resolution in Python unless C is needed.
- Let the native core load typelibs and shared libraries.
- Make generated modules importable without dynamic attribute tricks when
  possible.
- Keep `ginext.repository` out of the first native story unless compatibility
  work needs it.

Next: [[3 generated bindings]]

