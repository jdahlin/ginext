# What makes great GUI-toolkit programming books

Research notes to inform the structure of the goi/ginext book (`docs/book/`).
The target reader is a developer with little or no visual-design background
learning to build GTK 4 applications in Python via GObject Introspection.

The findings draw on a verified deep-research pass over Qt, GTK, and wxPython
book material plus a supplemental pass over the modern, actively-maintained
ecosystems (Apple iOS/macOS, Android, Electron, React Native). Sources are
listed at the end.

## TL;DR for our book

- **Target GTK 4 + PyGObject, never PyGTK.** PyGTK is GTK 2.x only and
  deprecated; GNOME explicitly says "do not use PyGTK for new projects" and
  "port to PyGObject." A book on PyGTK is obsolete on arrival.
- **There is no strong incumbent to imitate.** The GTK book canon is thin and
  stale (Krause's *Foundations of GTK+ Development* is 2007 / GTK 2). Steal the
  structural playbook from the active Apple / Android / web ecosystems instead.
- **Adopt the "build a real app, chapter by chapter, with graded challenges"
  model** (Big Nerd Ranch, Kodeco/raywenderlich), not the old GTK
  reference-manual style.
- **Plan for API churn from page one.** It is the single dominant reason these
  books die. Companion repo, version-pinning, errata channel, and isolation of
  version-volatile chapters (events, tooling).

## Canonical books and why they are regarded as good or weak

| Book | Ecosystem | Strength / weakness |
|---|---|---|
| *Rapid GUI Programming with Python and Qt* (Summerfield) | PyQt | Examples are "applications in their own right, rather than contrived ideas to illustrate a point." Front-loads a Python primer so later code is legible. |
| *C++ GUI Programming with Qt 4* (Blanchette & Summerfield) | Qt/C++ | Clean Hello-Qt → dialogs → main windows → custom widgets progression. Reference standard for sequencing. |
| *Foundations of GTK+ Development* (Krause, Apress 2007) | GTK (C) | Teaches GObject/inheritance early "to allow complete understanding of code examples later." Aged badly (GTK 2). |
| *wxPython in Action* (Rappin & Dunn) | wxPython | Blends tutorial + best-practices + reference, with dedicated lookup tables for properties/methods/events. |
| *Cocoa Programming for macOS* / *iOS Programming* (Big Nerd Ranch) | Apple | Famous for tiered Bronze/Silver/Gold end-of-chapter challenges; one interaction mechanism per chapter. Weak point: version drift breaks later chapters. |
| *100 Days of SwiftUI* (Paul Hudson) | SwiftUI | "Only the information needed at the right moment." Fixed daily rhythm: learn → review → challenge → consolidate. |
| Apple SwiftUI Tutorials (Landmarks) | SwiftUI | One evolving app, every step paired with live preview output. Risk: one broken step blocks everything after. |
| *Electron in Action* (Kinney) | Electron | One evolving app; packaging/distribution is a first-class final section. Aged via API churn (removed `remote` module). |
| *Fullstack React Native* (Abbott et al.) | React Native | Six distinct project apps, one per subsystem. Good isolation. |
| *Learning React Native* (Eisenman) | React Native | Clear intro, dedicated debugging chapter. Weak point: "almost every code sample is outdated" (ES5-era). |
| *Android Programming* (Big Nerd Ranch) / *Android Basics with Compose* (Google) | Android | BNR: 6 apps, longest spanning 11 chapters. Google codelabs: one app per codelab, `@Preview` instant feedback, deliberate "wrong code, run, fail, fix." Churn-criticized. |
| *The Busy Coder's Guide* (Mark Murphy) | Android | The churn answer: continuously updated by subscription; sequential "core path" separated from on-demand "trails." |

## The recurring structural playbook

These patterns recur across the strongest books and are the ones worth copying.

- **Difficulty-tiered, hello-world first.** Minimal window → basic widgets →
  layout → events/signals → dialogs/menus → models/views → custom widgets →
  advanced (threading, networking) → tooling/designer → packaging.
- **Front-load prerequisites.** Language primer and object-system fundamentals
  come before widget code, so examples are never opaque.
- **Real example apps, not snippets.** Two valid strategies, both proven; pick
  one and signpost it to the reader:
    - *One evolving app* (Apple Landmarks, Electron Firesale, React
      Tic-Tac-Toe): continuity, shows architecture growth, but fragile.
    - *Many scoped apps* (Fullstack RN's six, Krause's five capstones):
      modular, repetitive, resumable.
    - *Middle path* (Big Nerd Ranch): medium-lived apps spanning a chapter
      cluster. The most defensible compromise.
- **Teach the event model conceptually, problem-first.** Describe the main loop
  waiting on input, widgets emitting signals, callbacks connected to signals.
  Qt's docs motivate the notification problem and contrast signals against
  "unintuitive," type-unsafe raw callbacks. Do not dump the API.
- **Teach the object system before widgets.** For GObject specifically, convey
  signals' dual role (virtual-method override + notification), plus properties
  and reference counting, before any widget code.
- **Separate teaching narrative from reference.** Keep the tutorial
  productivity-focused; offload exhaustive API to tables/appendices or the
  official docs.
- **Layout placement depends on paradigm.** Imperative/constraint toolkits can
  defer layout (Cocoa pushes Auto Layout to ch. 25); declarative/compositional
  toolkits must front-load it (SwiftUI stacks, Compose). GTK 4 boxes/grids sit
  in between; lean toward teaching it early.
- **Packaging/distribution as a first-class final section,** not an
  afterthought. The single most-skipped topic in weak books.

## Pedagogical techniques worth stealing

- **Tiered end-of-chapter challenges** (Bronze/Silver/Gold, intentionally
  unsolved). The single most-praised feature of the Big Nerd Ranch series.
- **A predictable per-chapter loop:** runnable artifact → concept just-in-time →
  annotated "type this in and run it" with expected visual output shown →
  comprehension check → tiered challenges.
- **Pair every code step with its expected screenshot/preview.** Apple and
  Google exploit live preview (`@Preview`, Xcode canvas) for an instant
  code→see-result loop. For GTK, GTK Inspector plus a fast edit-run loop (and
  our hot-reload work) is the equivalent.
- **"Wrong code, run it, watch it fail, fix it."** Google's Compose codelab
  shows `var expanded = false // Don't do this!`, lets it fail to update, then
  introduces state. Felt failure beats assertion.
- **Discover the need before naming the concept** (React "lift state up"
  because a feature requires shared data). Motivation precedes machinery.
- **Name the paradigm/model explicitly** rather than letting the reader infer
  it. Even though GTK is largely imperative, naming the signal and
  property-binding model up front pays off.
- **Bridge design intuition via the toolkit's HIG reasoning, not design rules:**
  "use the standard widget because it already handles accessibility, state,
  theming, and animation; go custom and you own all of that." The cleanest way
  to give engineers taste without a design course.

## What makes these books fail or age badly

1. **API churn, the dominant failure mode.** GTK 4 broke API/ABI vs GTK 3,
   removed classes earlier books taught as fundamental (`GtkContainer`,
   `GtkBin`, the `GtkMenu` family, `GtkEventBox`, `GtkButtonBox`,
   `GtkToolbar`), and replaced widget input signals with event
   controllers/gestures (`button-press-event` → `GtkGestureClick`). A GTK 3
   signal-based events chapter needs a full rewrite for GTK 4. The same rot
   sank Eisenman (ES5) and Kinney (removed `remote` module).
2. **Building on a dead foundation** (PyGTK / GTK 2).
3. **Too much transcription, too little explanation.** Readers "spend more time
   typing than learning." Explain each block.
4. **Rushed final chapters and uneven difficulty.**
5. **No packaging/distribution and no UI-debugging coverage.**
6. **One-evolving-app fragility** with no resumable checkpoints.

Mitigations: companion git repo, errata/update channel, version-pinning, and
isolating version-volatile material (events, tooling) into clearly-marked
chapters. Murphy's continuously-updated model is the gold-standard answer.

## Proposed structure for the goi/ginext book

**Part I — Foundations**

1. Why GTK 4 + PyGObject, and the landscape (kill PyGTK confusion immediately).
2. Toolchain and first run: a minimal window, the edit-run loop, GTK Inspector.
3. GObject before widgets: objects, properties, reference counting, and
   signals' dual role (override + notification), front-loaded so all later code
   is legible.

**Part II — Building UI**

4. Core widgets (buttons, labels, entries), type-and-run, each paired with a
   screenshot.
5. Layout: boxes, grids, and composition (taught early; GTK 4 has no
   `GtkContainer`).
6. The signal/event model, problem-first: main loop → emission → callbacks;
   then event controllers and gestures (the GTK 4 way, not legacy `*-event`
   signals).
7. Dialogs, menus, and the `GAction` / `Gio.Menu` model.

**Part III — Real applications**

8. Lists and data: `GListModel` + `GtkListView`/`GtkColumnView` (the modern
   replacement for the old TreeView).
9. Custom drawing and custom widgets (`GtkSnapshot`).
10. The UI designer: hand-written `GtkBuilder` XML first, then Cambalache
    (Glade is deprecated), designer as a productivity layer on top of
    hand-coded understanding, introduced after the reader can build by hand.
11. Application architecture: `GtkApplication`, actions, settings (`GSettings`).

**Part IV — Shipping**

12. Debugging UI (GTK Inspector deep-dive), its own chapter, placed after
    fundamentals.
13. Packaging and distribution: Meson, GResource bundling, Flatpak, a
    first-class final section.

Throughout: one evolving example app (a small but real GNOME-style app)
supplemented by modular per-widget mini-examples; tiered unsolved challenges at
each chapter end; a companion repo and a version-pinning/errata strategy stated
in the preface to fight churn.

## Caveats on source strength

The technical claims (GObject docs, Qt docs, GTK4 migration guide, GNOME wiki)
are anchored by unanimous primary sources. The book-pedagogy specifics rest
partly on publisher pages and reviews, mitigated with independent reviews where
possible. The modern-ecosystem material (Apple/Android/Electron/RN) came from a
supplemental pass not run through the same adversarial verification as the core
report; treat evaluative phrasing as descriptive of structure, not
independently benchmarked quality.

## Sources

Structure and object/event model (verified primary sources):

- GObject concepts — <https://docs.gtk.org/gobject/concepts.html>
- Qt signals and slots — <https://doc.qt.io/qt-6/signalsandslots.html>
- GTK 3→4 migration guide — <https://docs.gtk.org/gtk4/migrating-3to4.html>
- PyGObject GTK4 tutorial — <https://pygobject.gnome.org/tutorials/gtk4.html>
- GNOME PyGTK project page — <https://wiki.gnome.org/Projects/PyGTK>
- PyGObject porting guide — <https://pygobject.gnome.org/guide/porting.html>
- GTK4 Python Tutorial — <https://github.com/Taiko2k/GTK4PythonTutorial>

Book pedagogy (publisher pages, reviews, official tutorials):

- Summerfield PyQt book — <https://mark-summerfield.github.io/pyqtbook.html>
- Foundations of GTK+ Development — <https://www.oreilly.com/library/view/foundations-of-gtk/9781590597934/>
- wxPython in Action — <https://www.manning.com/books/wxpython-in-action>
- Cocoa Programming for macOS — <https://www.oreilly.com/library/view/cocoa-programming-for/9780134077130/>
- 100 Days of SwiftUI — <https://www.hackingwithswift.com/100/swiftui>
- Apple SwiftUI tutorials — <https://developer.apple.com/tutorials/swiftui/creating-and-combining-views>
- Apple Human Interface Guidelines — <https://developer.apple.com/design/human-interface-guidelines/>
- Thinking in Compose — <https://developer.android.com/develop/ui/compose/mental-model>
- Jetpack Compose Basics codelab — <https://developer.android.com/codelabs/jetpack-compose-basics>
- Now in Android — <https://android-developers.googleblog.com/2022/05/now-in-android-sample-app-alpha.html>
- The Busy Coder's Guide — <https://www.amazon.com/Busy-Coders-Guide-Android-Development/dp/0981678009>
- Electron in Action — <https://www.manning.com/books/electron-in-action>
- Electron process model — <https://www.electronjs.org/docs/latest/tutorial/process-model>
- Learning React Native — <https://www.oreilly.com/library/view/learning-react-native/9781491989135/>
- Fullstack React Native — <https://www.newline.co/fullstack-react/react-native/>
- Thinking in React — <https://react.dev/learn/thinking-in-react>
