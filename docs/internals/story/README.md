# ginext Story

This directory is a small, ordered story for the next ABI2-only binding
implementation. The pages are meant to be readable in Obsidian, useful as
implementation notes, and eventually usable as doctest-backed examples.

The story should stay user-facing first. Each page answers one question:
"What does using ginext feel like at this stage?" Implementation notes can sit
under that, but the examples should drive the shape of the runtime and
generator.

## Pages

1. [[1 why ginext|Why ginext]]
2. [[2 importing namespaces|Importing namespaces]]
3. [[3 generated bindings|Generated bindings]]
4. [[4 objects methods and properties|Objects, methods, and properties]]
5. [[5 signals and ownership|Signals and ownership]]
6. [[6 files async and errors|Files, async, and errors]]
7. [[7 property bindings|Property bindings]]
8. [[8 subclassing later|Subclassing later]]
9. [[9 tests and doctests|Tests and doctests]]
10. [[10 typing by default|Typing by default]]
11. [[11 mapping rules|Mapping rules]]
12. [[12 binding member kinds|Binding member kinds]]
13. [[13 primitive and scalar values|Primitive and scalar values]]
14. [[14 non scalar values|Non-scalar values]]
15. [[15 goi cli|goi CLI]]

## Doctest Style

Use `pycon` blocks for examples that should eventually run:

```pycon
>>> from ginext import Gio
>>> Gio.__ginext_abi__
'native-v2'
```

Use regular `python` blocks for sketches that are not executable yet, rely on
platform behavior, or intentionally omit setup.
