# Why ginext

`ginext` is the from-scratch ABI2 binding. The current `goi` prototype taught
us the important contracts: invoke can work, native signals are a better user
surface, closure lifetime needs first-class modeling, and generated bindings
should exist from the start.

The next implementation should not begin as a compatibility layer with Python
features attached later. It should begin as the Python-native surface:

```python
from ginext import Gio, GObject
```

The compatibility question can be handled separately. `ginext` should optimize
for the code we want people to write next.

## Goals

- Target ABI2 only.
- Prefer Python implementations unless C is needed for correctness,
  performance, or ownership.
- Generate the public binding surface from GIR and overlays from the start.
- Keep low-level reference counting, closure trampolines, and GObject identity
  in a small native core.
- Reuse PyGObject ideas or code only where they still match the ABI2 shape.
- Preserve the current POC's working invoke lessons.
- Treat closure ownership as shared runtime infrastructure, not a signal-only
  feature.

## Non-goals

- Do not preserve every PyGObject spelling on the native surface.
- Do not hide ABI2 decisions behind dynamic magic if the generator can make the
  contract explicit.
- Do not start with broad GTK application coverage. Start with small GLib,
  GObject, and Gio slices that prove the runtime model.

## First User Promise

The first useful promise should be simple:

```python
from ginext import Gio

file = Gio.File("notes.txt")
data = await file.read_bytes()
```

That tiny example requires import resolution, generated classes, native object
wrapping, async finish pairing, error mapping, and hidden low-level GIR calls.
It is a good vertical slice because it exercises the real architecture without
starting in GTK.

Next: [[2 importing namespaces]]

