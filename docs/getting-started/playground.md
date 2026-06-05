---
title: Playground
description: A low-friction place to experiment with ginext APIs.
sidebar_position: 3
---

# Playground

The quickest way to learn the API is to run small experiments before you commit
to a full application structure.

## Import a namespace directly

For API exploration, start with a one-liner:

```sh
python -c "from ginext import Gio; print(Gio.File)"
```

or with GTK installed:

```sh
python -c "from ginext import Gtk; print(Gtk.Button(label='Open').label)"
```

That is often enough to confirm that the runtime and namespace packages are
installed correctly.

## Use the bundled examples

This repository already contains small apps and focused examples under
`examples/`. They are a better playground than an empty REPL when you want to
see real GTK, Gio, or async code paths.

Good starting points include:

- `examples/gio/file.py`
- `examples/async/with_asyncio.py`
- `examples/hello_template.py`
- `examples/playground/`

## Repository playground app

The draft playground app in
[examples/playground/README.md](https://github.com/jdahlin/ginext/blob/main/examples/playground/README.md)
is intended to become a richer workbench for trying `ginext` APIs and examples.

The README currently documents running it from source as:

```sh
uv run --project src/playground ginext-playground
```

That part of the repo is still a draft, but it is the right direction for a
real interactive exploration workflow.

## What to try first

- inspect a namespace import
- construct a simple Gio or Gtk object
- change a property and connect a signal
- run one bundled example before starting a full app
