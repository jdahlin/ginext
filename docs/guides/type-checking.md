---
title: Type Checking
description: Stubs, stub generation, and mypy integration for ginext.
sidebar_position: 12
---

# Type Checking

Type information is part of the intended `ginext` product surface, not an
afterthought. In practice that means two things:

- native `ginext` code should be checked against generated namespace stubs
- mypy should understand the `ginext` runtime surface closely enough that the
  checked API matches what users actually write

## The two packages to know

There are two separate pieces in this repository:

- `packages/ginext-stubgen` contains the generator and its CLI
- `packages/ginext-stubs` is the PEP 561 stub-only distribution that type
  checkers consume

The generator reads GIR XML and emits `.pyi` files for the native
`from ginext import Gtk` style surface.

## Using the published stubs

For application code, the important thing is the stub package, not the
generator internals.

The generated stubs are meant to make imports like this type-check correctly:

```python
from ginext import Gio, Gtk
```

The stub distribution is `ginext-stubs`, which exists specifically so type
checkers can resolve the dynamic namespace objects to real generated types.

## The stubgen CLI

The generator installs a console script named `ginext-stubgen`.

The main commands are:

```sh
uv run python -m ginext_stubgen generate GLib:2.0
uv run python -m ginext_stubgen generate-all
uv run python -m ginext_stubgen install
```

Those correspond to:

- `generate` for one or more explicit `NAMESPACE:VERSION` pairs
- `generate-all` for the default namespace set shipped by `ginext-stubs`
- `install` for `generate-all` followed by reinstalling the stub package into
  the active environment

By default, native stubs are written into
`packages/ginext-stubs/ginext/`.

## Regenerating stubs in this repository

For normal repo work, the easiest entry point is the Make target:

```sh
make stubs
```

That flow does the expected repository-local work:

- builds the in-tree test typelibs needed for generation
- runs `ginext-stubgen generate-all`
- reinstalls `packages/ginext-stubs` into the active environment

If you only want the raw generator step, run:

```sh
uv run ginext-stubgen generate-all
```

## What stubgen covers

The stub generator is not just emitting bare class names. It is intended to
cover the surfaces that matter for real `ginext` code, including:

- namespace functions, constants, aliases, and classes
- methods, constructors, properties, and virtual methods
- typed GObject signal surfaces
- out-parameter folding into tuple-style return types
- native and compat emission modes
- overlay-informed surface shaping where the generator has static knowledge of
  the runtime behavior

The longer design notes live in
[docs/stubgen.md](https://github.com/jdahlin/ginext/blob/main/docs/stubgen.md).

## The mypy plugin

This repository enables a mypy plugin at:

`src/ginext/mypy_plugin.py`

and wires it in through `pyproject.toml`:

```toml
[tool.mypy]
plugins = ["src/ginext/mypy_plugin.py"]
```

If you are type checking code against a source checkout rather than only an
installed wheel set, you should expect the plugin to be part of the supported
workflow.

## What to put in your mypy config

The repo config is the best reference point for now:

- add the relevant source roots to `mypy_path`
- enable the `src/ginext/mypy_plugin.py` plugin
- make sure the generated namespace stubs are installed in the environment
  mypy is running against

In this checkout, `mypy_path` includes `src/` plus the in-repo package sources,
and the plugin is enabled directly from the source tree.

## Practical workflow

For repo-local type-checking work, the normal sequence is:

1. regenerate or reinstall stubs if the namespace surface changed
2. run mypy with the repo config and plugin enabled
3. verify that the checked imports resolve to `ginext-stubs` rather than
   falling back to `Any`

If type checking suddenly becomes permissive in the wrong places, one of the
first things to check is whether `ginext-stubs` has been regenerated and
reinstalled into the environment mypy is using.
