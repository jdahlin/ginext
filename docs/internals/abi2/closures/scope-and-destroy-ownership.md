# Scope and destroy ownership

## Problem

GI callback arguments have different native lifetime scopes. The closure
implementation needs to route each scope through an explicit owner instead of
using one generic "keep it alive" rule.

`goi_callback_closure_new()` creates a libffi closure for a Python callable.
For `scope=call`, the invoke cleanup record frees the closure when the outer GI
call returns. For `scope=async`, the callback closure is released after the
one-shot callback fires. For `scope=notified`, omitted C user data carries the
closure cookie and the paired C destroy-notify slot releases it. `scope=forever`
still needs an explicit removal owner or is intentionally process-lifetime.

## Current shape

- `src/_goi/GObject/Closure-ffi.c` stores the closure cookie in
  `GoiArgCleanup.ptr` for all scopes. `scope=call` uses the cleanup kind;
  `scope=async` destroys after invoke; `scope=notified` uses the paired C
  destroy notify.
- `src/_goi/invoke/bind.c` uses that cookie to attach Python `user_data` to the
  callback closure.
- Destroy-notify companion slots are elided from Python, but when GIR exposes a
  `scope=notified` callback with a destroy slot, the native closure destroy
  function is passed to C.

## Why it matters

This is the hardest ownership gap because the binding hands native code a C
function pointer and then loses an authoritative record for when the callback
state should be released.

For async and notified APIs, freeing too early is worse than leaking, but leaks
make callback-captured Python objects survive longer than the native API owner.
The record inventory tests now assert that the expected owner path releases the
callable and removes the callback record.

## Issue references

- [#102](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/102):
  multiple callbacks may share the same destroy notifier; callback+destroy is
  not a unique closure identity.
- [#655](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/655):
  `Gio.Task.new(..., user_data)` shows that Python user data must survive until
  the native destroy notify runs.
- [#682](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/682):
  callback `user_data` conversion is part of the callable ABI, not a trailing
  convenience detail.
- [#758](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/758):
  callback, user-data, and destroy arguments form one logical group even when
  C ABI ordering is inconvenient.

## Broken example

```python
from goi.repository import Gio


def done(source, result, state):
    state["finished"] = True


state = {"finished": False}
file = Gio.File.new_for_path("example.txt")
file.query_info_async(
    "standard::name",
    Gio.FileQueryInfoFlags.NONE,
    0,
    None,
    done,
    state,
)
```

The callback and `state` must stay alive until the async operation completes.
After completion, both should be released exactly once. The async callback path
now releases after the callback fires; the notified path releases when native
code calls the paired destroy notify.

We are solving this so async and notified callback APIs can preserve Python
state until native completion without turning every callback into a permanent
process-lifetime reference.

## Needed design

ABI2 needs a callback closure record that can represent at least:

- call-scoped callback, freed after invocation returns to Python;
- async callback, owned by an in-flight native operation until completion;
- notified callback, owned until the native destroy notify runs;
- forever callback, deliberately process-lifetime or explicitly removable;
- destroy-notify callback, with Python state released exactly once.

The record must own the Python callable and `user_data`, install the correct C
destroy notify when GIR exposes one, and make cleanup idempotent.
