---
title: Guides
description: Task-oriented guides for building with ginext.
sidebar_position: 4
---

# Guides

The old introduction covered too many topics for a single page. In the docs
site, those topics work better as a small set of practical guides grouped by
task and area.

## In this section

- [Application structure](./application-structure.md) for organizing modules, UI
  files, resources, and app startup.
- [Constructors and namespaces](./constructors-and-namespaces.md) for the core
  object-model conventions.
- [Properties](./properties.md) for defining and using GObject properties.
- [Signals](./signals.md) for connection patterns, conflicts, and Python-defined
  signals.
- [Subclassing](./subclassing.md) for Python-defined GObject types, vfunc
  overrides, and automatic type naming.
- [Async support](./async-errors-and-event-loops.md) for the async-first I/O
  model and event-loop integration shape.
- [Gio](./gio.md) for files, settings, actions, cancellation, and D-Bus.
- [Pango](./pango.md) for font, layout, and text-structure patterns.
- [Gdk](./gdk.md) for value types, formats, and event-facing conveniences.
- [Gtk](./gtk.md) for templates, CSS, expressions, and text/widget patterns.
- [Type checking](./type-checking.md) for stubs, stub generation, and mypy plugin
  integration.
- [Concurrency](./concurrency.md) for async behavior, event loops, and
  free-threading expectations.
- [Migration from PyGObject](./migration-from-pygobject.md) for compatibility mode
  and selective adoption of native `ginext` APIs.

Readers looking for runtime speed and profiling guidance should start with the
top-level [Performance](../performance.md) page.

The goal is to keep `Guides` small enough to scan while still giving each topic
enough room to be useful.
