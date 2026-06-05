# goi CLI

The generator should be part of the `goi` CLI. `ginext` is the new binding
surface, but contributors should not have to remember a separate generator
module, script path, or Makefile target.

The CLI is the public contributor interface. Internal Python modules can move.

## Shape

Suggested top-level commands:

```sh
goi generate ...
goi lint ...
goi typecheck ...
goi package ...
```

`package` is intentionally TBD. It belongs in the command map now so packaging
decisions do not grow a separate tool later.

## Generate

Generate one namespace:

```sh
goi generate ginext --namespace Gio-2.0
```

Generate all checked-in ginext namespaces:

```sh
goi generate ginext --all
```

Check that generated files are up to date without writing:

```sh
goi generate ginext --all --check
```

Useful options:

```sh
goi generate ginext --namespace Gio-2.0 --write
goi generate ginext --namespace Gio-2.0 --stdout
goi generate ginext --namespace Gio-2.0 --explain File.read_bytes
```

`--explain` should print where a generated member came from:

- GIR callable/property/signal;
- ABI2 overlay file;
- hidden or public native status;
- generated runtime symbol;
- generated stub signature.

This is important for debugging mapping decisions.

## Lint

`goi lint` should check project-specific invariants that generic linters do not
understand:

```sh
goi lint ginext
goi lint overlays
goi lint docs
```

Good first lint checks:

- ABI2 overlays reference real GIR members;
- hidden native methods are absent from stubs;
- public generated names do not collide silently;
- generated docs link to existing story/reference pages;
- doctest snippets are either runnable or explicitly marked as sketches;
- generated files are up to date.

`ruff` should still handle normal Python style. `goi lint` is for binding
semantics.

## Typecheck

Type checking should also have a CLI front door:

```sh
goi typecheck examples/ginext --checker mypy
goi typecheck examples/ginext --checker pyright
goi typecheck examples/ginext --checker ty
goi typecheck examples/ginext --all
```

The command should print the underlying tool command. The wrapper is for common
configuration, not for hiding errors.

## Package

Packaging is TBD, but likely needs one command because generated files, native
extensions, typelibs, stubs, and docs must agree.

Possible future shape:

```sh
goi package wheel
goi package sdist
goi package inspect dist/goi-*.whl
```

Questions to resolve later:

- whether generated ginext files are checked in or produced during build;
- how much GIR/typelib metadata ships in wheels;
- how platform-specific native extension builds are named;
- how to verify `py.typed` and generated `.pyi` files are included;
- how to package docs and examples.

## Implementation Note

Eventually `pyproject.toml` should expose a console script:

```toml
[project.scripts]
goi = "goi.cli:main"
```

The first implementation can be minimal:

```sh
goi generate ginext --namespace Gio-2.0 --check
```

After that, add command groups when they remove real friction. Do not build a
large CLI framework before the generator has something useful to run.

