---
title: Gdk
description: Gdk value types, formats, and event-facing conveniences.
sidebar_position: 10
---

# Gdk

The `Gdk` surface in `ginext` focuses on making low-level value types and data
formats easier to use directly from Python.

## Value types

Types like `Gdk.RGBA` and `Gdk.Rectangle` should feel like normal Python value
objects with direct constructors and readable representations.

That makes them easier to create, inspect, print, and pass around in ordinary
application code.

## Content formats

`ContentFormats` is documented with collection-like behavior so that callers can
iterate and inspect it naturally instead of treating it as an opaque return
type.

## Texture downloading

The texture-downloader APIs are a good place to document named return values and
the expected Python shape of downloaded image data.

## Events

For GTK 3, the event surface also picks up convenience behavior around active
event arms and common constants. This belongs here because it affects how GDK
events feel in Python code.
