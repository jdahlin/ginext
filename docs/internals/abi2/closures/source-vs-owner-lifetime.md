# Source versus owner lifetime

## Problem

The object that owns a native closure is often not the same object users think
of as the logical lifetime owner.

Examples:

- `TreeSelection` signal source versus the visible `TreeView`;
- `Gtk.Builder` or template scope retaining callbacks;
- `SignalGroup` storing closures for changing targets;
- list item factories storing setup/bind/unbind callbacks;
- property bindings storing transform callbacks;
- async tasks storing completion callbacks;
- `Gtk.Expression` closures owned by expression objects.

## Current shape

ABI2 signal APIs have an explicit owner concept, but compatibility signal
closures are source-owned. Other callback families do not yet share the ABI2
owner-aware machinery.

`connect_object()` is the special case that already distinguishes source from
weak target: the source owns the signal connection, while the target dying
disconnects the handler.

## Why it matters

Cleaning up when the source dies is not enough if the source is a helper object
that outlives the visible owner. Cleaning up when the visible owner dies is not
possible unless the closure record knows that owner and has a way to remove or
invalidate the native closure.

This is the root of many callback retention issues: the callback captures the
logical owner, but native code stores the closure somewhere else.

## Issue references

- [#42](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/42):
  `TreeSelection` source lifetime differed from the visible `TreeView`.
- [#614](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/614):
  property bindings can retain transform closures and endpoint objects.
- [#634](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/634):
  model/factory callbacks can keep widgets alive after the window closes.
- [#736](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/736):
  templates create hidden child/callback graphs that affect finalization.
- [#735](https://gitlab.gnome.org/GNOME/pygobject/-/work_items/735):
  `Gio.SimpleAction` and `GObject.SignalGroup` style storage can own callbacks
  that capture the logical owner.

## Broken example

```python
class View(Gtk.Box):
    def __init__(self):
        super().__init__()
        self.selection = self.tree_view.get_selection()
        self.selection.connect("changed", self.on_selection_changed)

    def on_selection_changed(self, selection):
        ...
```

The visible lifetime owner is `View`, but the signal source is the
`TreeSelection`. If the selection object outlives the view, the closure can keep
the view alive. Cleaning up only when the source dies is too late; cleaning up
when the view dies requires a record that knows the logical owner separately
from the native source.

We are solving this because many real GTK callback owners are helper objects,
not the visible widget/controller the callback captures.

## Needed design

Every later-invoked ABI2 callback needs separate fields for:

- native source or storage owner;
- logical lifetime owner, if any;
- weak target, if any;
- removal/invalidation operation for the source.

APIs should make the logical owner explicit whenever it cannot be inferred.
