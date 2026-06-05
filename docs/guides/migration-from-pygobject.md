---
title: Migration from PyGObject
description: Compatibility mode and selective adoption of native ginext APIs.
sidebar_position: 14
---

# Migration from PyGObject

The old introduction mixed native API design with migration concerns. In the
docs site, migration guidance should stand on its own.

## Full compatibility mode

One migration path is a compatibility-oriented surface for projects that need a
PyGObject-like model first.

## Selective native adoption

Another path is to opt into native `ginext` behavior gradually, using the new
APIs where they provide a clearer or more Pythonic model without forcing an
all-at-once rewrite.

This guide should make those tradeoffs explicit so users can choose the right
migration strategy for their codebase.
