---
title: Constructors and Namespaces
description: Core object-model conventions in native ginext.
sidebar_position: 2
---

# Constructors and Namespaces

Native `ginext` keeps the shared GObject surface, but it tries to make the
different member kinds clearer in Python.

## Constructors

One of the main documentation topics here is the constructor story for GObject
types. The docs should explain what the default constructor shape is, how
keyword construction works, and where it intentionally differs from
PyGObject-style usage.

## Shared namespace

The shared namespace policy is a key conceptual difference:

- properties are accessed as attributes
- signals are accessed through signal objects
- methods remain callable methods

```python
obj.prop = value
obj.signal_name.connect(callback)
obj.method()
```

That split is important for discoverability and for making the kind of member
visible at the call site.
