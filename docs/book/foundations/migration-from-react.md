# Migration from Web / React

> GTK is **retained mode**: you build a widget tree once and mutate it. There is no re-render, no virtual DOM, no reconciliation. Internalize that one sentence and the rest of this guide is just vocabulary.

## The headline shift

In React you describe what the UI should look like for a given state, and the framework figures out the DOM mutations. In GTK you *make* the DOM mutations. There is no `render()` function that runs every time state changes.

| You used to write… | In GTK you… |
| --- | --- |
| `setCount(c + 1)` and let React re-render | Set a property; bound widgets update via `notify::` |
| A new array passed to a list component | Mutate a `Gio.ListStore` (append/remove/splice) and the view updates the affected rows |
| Conditional JSX (`{showX && <X/>}`) | Show/hide a widget, or use a `Gtk.Stack` |

## Concept map

| React / Web | GTK / goi |
| --- | --- |
| Component | Custom widget class / template |
| JSX | Blueprint or `.ui` XML |
| `useState` | `GObject.Property` |
| `useEffect` | `notify::` signal handler |
| Props | Constructor args / properties |
| Context API | Application-level singletons or actions |
| `useReducer` | Plain Python; or `Gio.SimpleAction` for shell-integrated state |
| React Router | `Adw.NavigationView` / `Adw.ViewStack` |
| CSS / styled-components | GTK CSS (subset, no flex/grid in CSS — use containers) |
| `fetch` | `Gio.File`, `libsoup` |
| `localStorage` | `GSettings` |
| `onClick` | `clicked` signal |
| `useRef` | Just keep a Python reference |
| `key=` prop on list items | `Gio.ListModel` identity / sections |

## What this chapter covers

- The retained-mode mental shift, with one good example showing the "wrong" React-shaped GTK code and the right version.
- "Where does state live?" — properties on widgets vs application objects; when to use bindings.
- Forms and inputs: there's no controlled/uncontrolled distinction; widgets *are* the state.
- Layout without flexbox: `Gtk.Box`, `Gtk.Grid`, alignment, hexpand/vexpand.
- Routing: `Adw.NavigationView` and friends.
- Async data fetching with `Gio` instead of `fetch`.
- Styling: what GTK CSS supports and what it doesn't.

## Worked example

Port a tiny React app (a todo list, with add/remove/toggle/persist) to goi.

## Notes for the writer

- Many readers will be coming from Electron specifically. Address "why not just Electron?" honestly: native look, RAM, battery, startup.
- Show the GTK CSS subset early — readers will want to style first thing and need to know what works.
- Don't pretend GTK has a virtual DOM. The honest answer is "you mutate the tree."
