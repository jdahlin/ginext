---
title: Why A New API?
description: Why ginext is aiming for a different Python surface.
sidebar_position: 2
---

# Why A New API?

`ginext` is not trying to wrap GObject Introspection with a thinner Python
spelling. The goal is a Python API that is easier to learn, easier to read, and
more consistent across GTK, Gio, and Python-defined types.

## The short version

The existing introspection ecosystem works, but it exposes a lot of history:

- APIs that read like C with Python syntax layered on top
- multiple ways to reach the same concept
- signal, property, and method surfaces that are not clearly separated
- async APIs that often make the non-blocking path feel secondary
- weak typing and awkward IDE support

`ginext` is trying to keep the power of the underlying platform while making
the Python layer feel more intentional.

## What is being changed

The main direction is not "new for the sake of new". It is a set of concrete
surface changes.

- Properties should look like normal attributes.
- Signals should be explicit signal objects rather than stringly-typed method
  calls.
- Async support should feel native instead of bolted on.
- Subclassing should line up with Python class syntax and `do_*` overrides.
- Typing should be part of the main product surface.
- Overlays should make targeted API cleanup possible without forking the whole
  binding story.

## Why not only compatibility mode

Compatibility mode is useful for migration, but it cannot be the whole design
goal.

If the only target is PyGObject compatibility, the result keeps many of the old
shapes that make the API harder to teach and harder to evolve. `ginext` wants a
native API that stands on its own, while still providing compatibility paths
where they are useful.

## Why overlays matter

One of the practical reasons a new API is viable is the overlay system.

Overlays let `ginext` improve specific constructors, methods, properties,
defaults, async return shapes, and Python protocol behavior without pretending
that the raw typelib surface is already the best possible Python API.

See [Advanced Guide](./advanced-guide/index.md) and [Overlays](./advanced-guide/overlays/index.md)
for the concrete mechanisms.
