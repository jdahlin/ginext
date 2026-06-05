---
title: Gio
description: Practical Gio patterns in ginext.
sidebar_position: 8
---

# Gio

`Gio` is where a lot of application-facing work happens in `ginext`: files,
applications, actions, settings, cancellation, async operations, and D-Bus.

## File operations

`Gio.File` is meant to work with a shorter, more Python-friendly call shape
than the raw introspection surface.

Typical code can focus on the operation itself:

```python
info = file.query_info("standard::*")
target.copy(destination)
child = directory / "notes.txt"
```

Two important conveniences here are:

- common `flags` and `cancellable` arguments can often be omitted
- `Gio.File` supports `/` for relative path resolution

Local files also participate in Python path-like APIs through `__fspath__()`.

## Applications and actions

`Gio.Application.run()` is intended to be a straightforward Python entry point.
Action APIs also get a more convenient shape, especially when registering many
actions at once.

This is part of the general `ginext` approach: common application setup should
read like normal Python application code rather than a repeated low-level call
sequence.

## List models

`ListModel` and `ListStore` are exposed with Python collection-style behavior.

That means you can write:

- `len(model)`
- `for item in model`
- `model[index]`
- `item in store`

instead of repeatedly spelling `get_n_items()` and `get_item()`.

## Settings

`Gio.Settings` is designed to feel more like a mapping:

```python
theme = settings["theme"]
settings["theme"] = "dark"
```

The schema still matters, and invalid keys or values should fail, but the
everyday usage should be much less ceremonial.

## Cancellation

`Gio.Cancellable` supports context-manager usage:

```python
with Gio.Cancellable() as cancellable:
    ...
```

This gives async or cancellable work a direct Python scope instead of forcing
manual push/pop handling.

## D-Bus

The D-Bus surface is one of the clearest places where `ginext` tries to improve
the default Python experience.

Current conveniences include:

- awaitable bus and proxy creation
- easier proxy method calls
- direct access to cached proxy properties
- context-managed signal subscriptions and object registrations

That keeps D-Bus code closer to normal Python async and resource-management
patterns.
