---
title: Pango
description: Pango text and layout conveniences in ginext.
sidebar_position: 9
---

# Pango

The `Pango` guide is where text layout and font-related Python conveniences
should be documented.

## Font descriptions

`Pango.FontDescription` should support the obvious Python-facing construction
and display patterns, including string-based construction and readable reprs.

## Iterable text structures

Several Pango types are easier to use when documented as iterable or
collection-like values, especially:

- `TabArray`
- `AttrList`

## Named return values

Layout and cursor-position APIs often return structured data. In `ginext`, the
goal is that those results should be easier to read than raw anonymous tuples,
so this page should document the expected named-result shapes.
