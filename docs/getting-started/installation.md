---
title: Installation
description: Installing ginext and choosing the right package surface.
sidebar_position: 1
---

# Installation

`ginext` is split into a core package plus optional namespace packages. The
core package gives you the binding runtime, and packages such as
`ginext-gio` or `ginext-gtk` add the higher-level namespace overlays and
typed surfaces for those libraries.

## Choose a starting package set

For a minimal install:

```sh
pip install ginext
```

For Gio support:

```sh
pip install ginext ginext-gio
```

For GTK applications:

```sh
pip install ginext ginext-gio ginext-gtk
```

If you are working from this repository, the optional dependency groups are
also exposed as extras in the project metadata:

```sh
pip install "ginext[gio]"
pip install "ginext[gio,gtk]"
```

## Python version

This project currently targets Python `>=3.14`, so the first installation check
is making sure you are using a supported interpreter.

## Verify the environment

After installation, verify that imports work:

```sh
python -c "from ginext import GLib; print(GLib)"
python -c "from ginext import Gio; print(Gio.File)"
python -c "from ginext import Gtk; print(Gtk.Button)"
```

Use the last two only if you installed the corresponding namespace packages.

## When compatibility packages matter

If you need the older `gi.repository` compatibility layer rather than the
native `ginext` API, install the compat package separately instead of assuming
the core package provides it by default.

That path belongs in migration scenarios, not as the default recommendation for
new code.

## Working from this checkout

In this repository, the normal development flow uses `uv` and the workspace
packages:

```sh
uv sync
uv run python -c "from ginext import Gio, Gtk; print(Gio.File, Gtk.Button)"
```

That is the quickest way to get a local docs or examples workflow running from
source.
