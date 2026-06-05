# Template API Design

This note describes the current native `ginext-gtk` template implementation
after removing `Gtk.Template.Callback()`, moving template metadata into the
generic `gimeta.extensions` bucket, and refactoring the runtime around a
Gtk4-first `TemplateRuntime`.

The important constraints are:

- keep the public surface as `Gtk.Template(...)` and `Gtk.Template.Child(...)`
- keep the UI file as the source of truth for signal hookup
- keep template policy out of core `ginext-gtk` when that policy can live in a
  user extension
- store Gtk-specific template metadata under `cls.gimeta.extensions["Gtk"]`
- keep Gtk4 as the primary implementation target; Gtk3 remains a small fallback

## Current Native Surface

Example:

```py
@Gtk.Template(resource_path="/com/example/app/window.ui")
class Window(Gtk.Window):
    title_label: Gtk.Label = Gtk.Template.Child()
    save_button: Gtk.Button = Gtk.Template.Child()

    def on_save_button_clicked(self, button: Gtk.Button) -> None:
        ...
```

The UI file remains authoritative:

```xml
<object class="GtkButton" id="save_button">
  <signal name="clicked" handler="on_save_button_clicked"/>
</object>
```

There is no callback decorator. The runtime reads the declared
`handler="..."` name from the template and resolves that method directly on the
Python instance.

## Type Naming

`__gtype_name__` is compatibility-only and should not be part of the native
template story.

For native template classes, the registered type should default to
`cls.__name__`, and duplicate registration should fail with a location-aware
diagnostic rather than auto-disambiguating silently.

Desired error shape:

```py
TypeError(
    "Could not register type for Window in foo.py, it has already been "
    "registered at bar.py:34"
)
```

## `Gtk.Template(...)`

```py
Gtk.Template(
    *,
    string: str | bytes | None = None,
    filename: str | os.PathLike[str] | None = None,
    resource_path: str | None = None,
    validate: Literal["strict", "warn", "ignore"] = "strict",
    connect_signals: bool = True,
)
```

Decorator rules:

- exactly one of `string`, `filename`, or `resource_path`
- `resource_path` expects a registered GResource path
- `validate` is one shared policy for child and signal mismatches
- `connect_signals=True` means connect `<signal>` declarations automatically
- `connect_signals=False` means parse and store the signal metadata, but leave
  hookup to user code
- native `ginext-gtk` no longer provides `from_string()`, `from_file()`, or
  `from_resource()` helpers

## `Gtk.Template.Child(...)`

```py
Gtk.Template.Child(
    name: str | None = None,
    *,
    internal: bool = False,
)
```

Semantics:

- default lookup name is the Python attribute name
- `name=` overrides the template child name
- `internal=True` preserves GTK's internal-child distinction
- the Python type annotation is the typing story for the instance attribute

## Metadata Storage

Gtk template state should not spill into ad hoc `__gtk*__` attributes on user
classes. The stable storage point is:

```py
cls.gimeta.extensions["Gtk"]
```

Current bucket shape:

```py
{
    "template": TemplateRuntime(...),
}
```

The important part is that the parsed template information is available through
one runtime object rather than several parallel dict entries.

The `TemplateRuntime` currently carries:

- `source: TemplateSource`
- `children: list[TemplateChild]`
- `signals: list[TemplateSignal]`
- `validate`
- `connect_signals`
- `base_init_template`

and methods for:

- class registration and hook installation
- instance initialization
- handler resolution
- Gtk4 builder-scope closure creation
- Gtk3 fallback signal hookup

## Initialization Order

Initialization should happen in this order:

1. load template bytes
2. parse the XML root
3. rewrite the `<template class="...">` attribute to `cls.gimeta.type_name`
4. build `TemplateRuntime`
5. store that runtime in `cls.gimeta.extensions["Gtk"]["template"]`
6. install the template bytes on the widget class
7. register one post-construction hook in `cls.gimeta.extensions["core"]`
8. construct the instance
9. run `init_template()`
10. bind children to instance attributes
11. if `connect_signals=True`, connect the parsed signal declarations

This guarantees that child attributes exist before handlers run.

## Runtime Shape

The runtime is Gtk4-first.

Gtk4:

- one module-level `TemplateBuilderScope(Gtk.BuilderCScope)` type
- one per-class `TemplateRuntime`
- builder closure creation goes through `runtime.create_closure(...)`

Gtk3:

- reuses the same `TemplateRuntime`
- installs a small `set_connect_func(...)` shim
- should be treated as fallback compatibility code, not the primary design

This keeps the main structure centered on the Gtk4 builder-scope model rather
than trying to give Gtk3 and Gtk4 equal architectural weight.

## Resource-Backed Templates

`resource_path` is the supported path for bundled templates:

```py
Gio.Resource.load("myapp.gresource")._register()

@Gtk.Template(resource_path="/com/example/app/window.ui")
class Window(Gtk.Window):
    main_button: Gtk.Button = Gtk.Template.Child()
```

If an application compiles resources into a binary, registration still happens
outside the decorator. The decorator only consumes the GTK resource path.

## Extension Surface

The extension story should be explicit: `ginext-gtk` provides the template
metadata and the default XML-driven hookup policy, but users should be able to
layer their own policy on top.

The supported substrate is:

- `cls.gimeta.extensions["Gtk"]["template"]`
- `connect_signals=False` to stop the default signal hookup
- a wrapper decorator that reads the stored `TemplateRuntime` and applies a
  custom policy

This keeps toolkit-specific policy out of core `ginext-gtk`.

## Example: Autoconnect Extension

This is the motivating example for a user-defined extension: support old
Builder or Kiwi-style autoconnect naming, but do it outside `ginext-gtk`
itself.

Desired use:

```py
@AutoTemplate(resource_path="/com/example/app/window.ui")
class Window(Gtk.Window):
    save_button: Gtk.Button = Gtk.Template.Child()

    def on_save_button_clicked(self, button: Gtk.Button) -> None:
        ...
```

The important part is that `AutoTemplate` is not a new core primitive. It is a
thin wrapper around `Gtk.Template(..., connect_signals=False)` plus a second
pass over the stored `TemplateRuntime`.

### Proposed Helper API

Provide a documented recipe shaped like this:

```py
from typing import Any

from ginext import Gtk


class AutoTemplate:
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("connect_signals", False)
        self._template = Gtk.Template(**kwargs)

    def __call__(self, cls: type) -> type:
        cls = self._template(cls)
        runtime = cls.gimeta.extensions["Gtk"]["template"]
        cls.gimeta.extensions["Gtk"]["autoconnect_policy"] = "method-name"

        original_init_template = cls.init_template

        def init_template(self: Any) -> None:
            original_init_template(self)
            _autoconnect_template_signals(self, runtime)

        cls.init_template = init_template
        return cls
```

With a helper:

```py
def _autoconnect_template_signals(obj: Any, runtime: Any) -> None:
    for signal in runtime.signals:
        handler_name = signal.handler_name
        handler = getattr(obj, handler_name, None)
        if handler is None:
            continue

        if signal.object_id is None:
            continue
        target = getattr(obj, signal.object_id)
        bound_signal = target._compat_signal_for_name(signal.signal_name)
        bound_signal.connect(handler, after=signal.after, owner=obj)
```

This recipe is deliberately plain Python. The extension author can replace the
handler resolution policy, validation policy, or connect timing without
changing `ginext-gtk`.

### Why This API

The extension contract should be small:

- `Gtk.Template(..., connect_signals=False)` prevents the default hookup
- `cls.gimeta.extensions["Gtk"]["template"]` exposes the stored runtime and its
  parsed signal metadata
- the extension decides how to resolve and connect handlers

That is enough to support:

- strict method-name autoconnect
- namespace-based lookup
- mixin-based policies
- logging or diagnostics
- delayed connection after additional setup

### Non-Goals For Core `ginext-gtk`

`ginext-gtk` itself should not:

- add a second built-in autoconnect convention
- scan all methods for `on_*`
- guess signal handlers that are not declared in XML or Blueprint
- own policy that belongs in project code

It should only provide the substrate.

## Plan

1. Keep `Gtk.Template` and `Gtk.Template.Child` as the only core public
   template API.
2. Finalize `Gtk.Template(..., connect_signals=False)` as the official escape
   hatch for custom policies.
3. Treat `cls.gimeta.extensions["Gtk"]` as the documented template metadata
   bucket.
4. Add a short reference example of a custom decorator like `AutoTemplate` in
   the docs.
5. Keep autoconnect itself out of `ginext-gtk` core unless a later use case
   proves the extension surface is insufficient.
