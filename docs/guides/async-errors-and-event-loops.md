---
title: Async Support
description: Async-first I/O, explicit sync APIs, and event-loop integration.
sidebar_position: 7
---

# Async Support

`ginext` should document async I/O as the natural default for new code rather
than an optional extra.

## Async-first APIs

The intended model is that common Gio operations are awaitable:

```python
import asyncio
from ginext import Gio


async def main():
    try:
        file = Gio.File(path="/tmp/test.txt")
        content = await file.load_contents()
    except FileNotFoundError:
        print("File not found")
    except PermissionError:
        print("Permission denied")
    else:
        print(f"File content for: {file} is {content[:30]!r}")


asyncio.run(main())
```

## Explicit sync APIs

When synchronous behavior is needed, the docs should point to explicit sync
variants such as `*_sync()` instead of making blocking behavior the default.

## Event loop integration

This guide should explain how `ginext` expects to integrate with the active
event loop and what that means for applications that mix GTK, Gio, and Python
async code.

## Exceptions and messages

The error-handling model belongs here too:

- how `GError`-style failures map to Python exceptions
- how exception types should feel natural in Python code
- what good runtime error messages look like for misused APIs
