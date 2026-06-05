# Events and input

> GTK4 replaced low-level "event" callbacks with high-level **event controllers**. You attach a controller to a widget and connect to its semantic signals (`pressed`, `dragged`, `key-pressed`) instead of handling raw events.

## What this chapter covers

- Why GTK4 changed: the GTK3 "event" model and its problems; what controllers solve.
- The controllers you'll use most:
    - `Gtk.GestureClick` — primary/secondary clicks.
    - `Gtk.GestureDrag` — click-and-drag.
    - `Gtk.GestureLongPress` — touch and long-hold patterns.
    - `Gtk.GestureZoom`, `Gtk.GestureRotate`, `Gtk.GestureSwipe` — multi-touch.
    - `Gtk.EventControllerKey` — keyboard.
    - `Gtk.EventControllerFocus` — focus enter/leave.
    - `Gtk.EventControllerMotion` — pointer motion / enter / leave.
    - `Gtk.EventControllerScroll` — scroll wheels and touchpads.
- Propagation phases: capture vs bubble; when to use each.
- Modifiers and pointer state from controllers.
- The `Gdk.Event` object: how to get it from a controller, what fields exist, what's been deprecated since GTK3.
- A worked example: a custom widget that responds to clicks, drags, and keyboard.

## What you'll be able to do

- Add interactive behavior to any widget without subclassing.
- Pick the right controller for a given interaction.
- Read modifier state and event coordinates from controller signals.

## Notes for the writer

- Many readers will arrive with stale GTK3 knowledge (`button-press-event`). Address that head-on early.
- Show one example per controller, short.
- Cross-link to the [Drag and drop](drag-and-drop.md) chapter (controllers are also how DnD works in GTK4).
