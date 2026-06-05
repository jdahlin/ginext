---
title: Gtk
description: Practical Gtk patterns in ginext.
sidebar_position: 11
---

# Gtk

The `Gtk` guide is about the high-level widget and UI-building experience in
`ginext`.

## Templates

`ginext` exposes `Gtk.Template` directly as part of the main GTK surface. This
should be the natural place to document template-based widget classes, child
lookup, and how UI files fit into an application structure.

## CSS

The CSS provider APIs are meant to accept Python-friendly text and bytes inputs
without making the caller care about low-level ABI details.

That makes `Gtk.CssProvider` a more natural place for application styling code.

## Expressions

GTK 4 expression APIs are important enough to deserve explicit documentation.

In `ginext`, the goal is that expressions should be easier to construct from
Python-facing values such as:

- property descriptors
- `ParamSpec` values
- property-name strings
- simple attribute paths

That makes expression-based binding more approachable in normal application
code.

## Text and tree helpers

The GTK text stack also gets Python-oriented conveniences for areas like:

- `TreePath`
- `TextBuffer`
- `TextIter`

These should be documented here as normal Gtk usage patterns rather than as
overlay implementation details.

## GTK 3 compatibility

There are also GTK-3-specific compatibility surfaces for builders, dialogs,
legacy widget/container helpers, and older action APIs. Those should be
documented as GTK 3 material rather than treated as the default GTK 4 path.
