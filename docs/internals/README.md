# Internals

This directory contains implementation-specific design notes, architecture
plans, research notes, and development checklists for goi/ginext.

Use these documents when changing how the runtime is built or how compatibility
is implemented. User-facing guide material stays under `docs/book/`; imported
research snapshots stay under their source-specific directories.

## Runtime And Architecture

- [Runtime restructure plan](project_runtime_restructure.md)
- [ABI modes design](abi-modes.md)
- [Native and compat surface plan](native-compat-surface-plan.md)
- [ABI2 native surface](abi2/abi2.md)
- [Compiled overlays design](overlays.md)
- [Typelib versioning and stub generation](typelib-versioning.md)

## Invocation, JIT, And Performance

- [Invoke refactor plan](invoke-plan.md)
- [Invoke and marshaller architecture analysis](invoke-marshaller-analysis.md)
- [Invoke vectorcall revival plan](invoke-vectorcall-revival.md)
- [Full JIT implementation plan](full-jit-plan.md)
- [Closure JIT plan](closure-jit-plan.md)
- [JIT specialization TODO](todo-2026-05-10-jit-specialize.md)
- [GObject.Property optimization notes](gobject-property-optimizations.md)
- [Code duplication checks](code-duplication.md)

## Compatibility And Research

- [Testing PyGObject compatibility](testing-compat.md)
- [PyGObject architectural issues](pygobject-architectural-issues.md)
- [PyGObject lifetime and GC notes](pygobject-lifetime-gc-notes.md)
- [Reference counting notes](ref-counting.md)
- [Async test targets](async-test-targets.md)

## Feature And API Design

- [ginext story](ginext/story/README.md)
- [ginext namespace/class/method/invoke plan](ginext-namespace+class+method+invoke-plan.md)
- [Template API design](template-api-design.md)
- [GitLab agent setup](gitlab-agent-setup.md)
- [Async runtime (implementation + decisions)](async-runtime.md)
- [Async cancellation design](async-cancellation.md)
- [GTK Expression mapping](gtk-expression.md)
- [GTK ColumnView ergonomics](gtkcolumnview.md)
- [Hot reload for GObject subclasses](hot-reload.md)
- [Runtime docstrings plan](goi-docs-plan.md)
- [Future features](future-features.md)
- [Documentation site ideas](doc-ideas.md)
- [What makes great GUI-toolkit books (book structure research)](book-structure-research.md)

## Working Notes

- [Current TODO](TODO.md)
- [Memory index](MEMORY.md)
- [Conceptual integrity review](todo-2026-05-10.md)
