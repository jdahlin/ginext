# Migration from SwiftUI

> SwiftUI and GTK both produce native UI, but they're built on opposite philosophies: SwiftUI is declarative and rebuilds view trees from state; GTK is retained and mutates a persistent widget tree. The vocabulary maps; the mental model needs translation.

## The headline shift

SwiftUI `body` re-evaluates when state changes; the framework diffs and updates. In GTK there is no `body` — you create widgets once, then mutate them (or let property bindings propagate changes). Familiar SwiftUI patterns like "compute view from state" still work *conceptually*, but the implementation is property bindings rather than view rebuilds.

## Concept map

| SwiftUI | GTK / goi |
| --- | --- |
| `View` (struct) | `Gtk.Widget` (class) |
| `@State` | `GObject.Property` |
| `@Binding` | `GObject.bind_property` (`GBinding`) |
| `@ObservedObject` / `@StateObject` | Any `GObject.Object` + `notify::` |
| `@Environment` | Application-level singletons or actions |
| `ViewBuilder` | Imperative tree construction; or Blueprint |
| Modifier chains (`.padding().background(...)`) | Property assignments + CSS classes |
| `NavigationStack` | `Adw.NavigationView` |
| `List` | `Gtk.ColumnView` / `Gtk.ListView` with factories |
| `Form` | `Adw.PreferencesPage` |
| `Toggle`, `Picker`, `Stepper` | `Gtk.Switch`, `Gtk.DropDown`, `Gtk.SpinButton` |
| Combine publishers | GObject signals + `Gio.Task` |
| `.task { … }` | `Gio` async + `asyncio` (where goi bridges) |
| `.sheet`, `.alert` | `Adw.Dialog`, `Adw.MessageDialog` |
| Property wrappers | No direct analog — use plain methods/properties |
| Preview canvas | Hot-reload via Cambalache for `.ui`; otherwise just re-run |

## What this chapter covers

- Declarative → retained: how to think about state without `body` rebuilding.
- Bindings: `GBinding` as the closest cousin to `@Binding`.
- Navigation: `NavigationStack` patterns in `Adw.NavigationView`.
- Lists with factories: the mental shift from "data → views" to "register a factory that builds views per row."
- Modifiers vs CSS classes: how to get the same visual effect without modifier chains.
- Async work: where Swift Concurrency fits with GIO async patterns.
- Why GTK templates ≠ SwiftUI previews, and what to use instead.

## Worked example

Port a small SwiftUI app (a settings screen + a master/detail navigation) to goi.

## Notes for the writer

- Pin SwiftUI on iOS 17 / macOS 14.
- Many SwiftUI devs are coming from iOS — be explicit that GTK is desktop-first; mobile via Phosh is real but secondary.
- Acknowledge what SwiftUI does better (animations, previews) and where GTK wins (cross-distro, runs on Linux/Windows/macOS without Apple's stack).
