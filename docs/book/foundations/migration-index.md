# Migration guides

> If you've built UI in another ecosystem, you don't need to start from scratch — you need a translation. Pick the guide that matches your background.

## Available guides

- [From Qt / PySide](migration-from-qt.md) — the closest mental model: signals/slots, QObject properties, models.
- [From Web / React](migration-from-react.md) — biggest conceptual shift is **retained mode vs immediate mode**. Read this first if you're coming from JSX.
- [From SwiftUI](migration-from-swiftui.md) — also a declarative-to-retained shift, but with a different property/binding model.
- [From PyGObject](migration-from-pygobject.md) — what's the same, what's different, what to watch for when porting.

## How to use these guides

Each guide opens with a concept-mapping table (your world → GTK world) and works through small examples that translate idioms you already know. They are intentionally repetitive across guides — readers don't read all four; they read one.

## Notes for the writer

- Each guide should end with a worked example: port one small app from the source framework to GTK + goi.
- Resist mentioning frameworks the reader didn't come from. The Qt guide should not explain React-isms.
- Pin a version of the source framework (Qt 6, React 18, SwiftUI on iOS 17) so analogies don't drift.
