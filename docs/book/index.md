# goi

> A book on building GTK and GNOME apps with Python — using **goi**, a GObject-Introspection–based binding.

This book teaches GTK app development end to end: from a "Hello World" window to publishing on Flathub, from raw GTK on Windows to a polished GNOME Circle app, and from `Gtk.Button` all the way down to writing your own GObject types in C.

## Who this book is for

- **Python developers** who want to build native desktop apps and don't know where to start.
- **App developers from other ecosystems** (Qt, React/Electron, SwiftUI) who want a guided translation rather than a from-scratch tutorial.
- **PyGObject users** who want to know what's different in goi and when to switch.
- **GNOME app authors** who want one place that covers the *whole* platform — not just libadwaita.

## How the book is organized

The book is divided into nine Parts. The first three are pan-platform GTK. Part IV is the opinionated GNOME path. Part V covers everything that isn't GNOME. The rest cover going deeper, extending the binding, and shipping.

| Part | What it covers |
| --- | --- |
| **I — Foundations** | Install, hello world, GObject, migration guides |
| **II — Building GTK apps** | Widgets, events, declarative UI, async, dialogs, lists |
| **III — System integration** | Portals, DBus, system services, settings, notifications |
| **IV — Writing GNOME apps** | The GNOME platform end to end: HIG, Blueprint, libadwaita, accessibility, Flathub, Circle |
| **V — Beyond GNOME** | Windows, macOS, KDE, elementary, sway, Phosh |
| **VI — Going deeper** | Cairo, Gsk, custom widgets, performance |
| **VII — Extending goi** | Writing C/Rust extensions, overlays, FFI pitfalls |
| **VIII — Shipping** | i18n, packaging for every target, CI/CD |
| **IX — Reference** | API reference, Pango/HarfBuzz/FreeType, glossary |

## How to read it

Read Parts I–III in order. After that, pick the Part that matches what you're shipping.

## Notes for writers (remove before publish)

- All chapters start as stubs with: a framing paragraph, a "What this covers" outline, "What you'll be able to do," and writer notes.
- Code examples should be runnable; long ones should live in `apps/` or `examples/` and be pulled into docs via snippet macros.
- Each migration guide ends with a worked "port this small app" example.
