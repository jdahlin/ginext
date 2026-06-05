---
title: Concurrency
description: Event loops, async behavior, and free-threading expectations.
sidebar_position: 13
---

# Concurrency

Concurrency deserves its own page instead of being folded into a tooling
overview.

## What this page should cover

- async-first Gio and GLib usage
- event loop integration
- blocking versus explicit sync calls
- callback lifetime and reentrancy expectations
- free-threading considerations

This page should connect the high-level concurrency model to the practical rules
that app authors need when mixing GTK, Gio, and Python async code.
