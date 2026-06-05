# Tests And Doctests

The story pages should eventually be executable, but they should not replace
focused tests. Use the story doctests to pin the narrative and focused pytest
files to pin edge cases.

## Test Layers

1. Story doctests: small examples that show how ginext should feel.
2. Generator tests: generated runtime tables and `.pyi` output.
3. Runtime unit tests: object wrapping, invoke, properties, signals, closures.
4. Integration slices: `Gio.File`, async streams, error mapping.
5. Later application tests: small GTK examples, then real applications.

## Story Doctest Wrapper

The wrapper can start as an expected failure while ginext is still being built:

```python
from __future__ import annotations

import doctest
from pathlib import Path

import pytest


@pytest.mark.xfail(strict=True, reason="ginext story drives the implementation")
def test_ginext_story_doctests():
    root = Path(__file__).parents[1] / "docs" / "ginext" / "story"
    failures = 0
    def story_number(path: Path) -> int:
        return int(path.name.split(" ", 1)[0])

    for path in sorted(root.glob("[0-9]*.md"), key=story_number):
        result = doctest.testfile(
            str(path),
            module_relative=False,
            optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE,
        )
        failures += result.failed
    assert failures == 0
```

## What Belongs In Doctests

Good doctest examples:

- imports;
- simple method calls;
- property read/write;
- signal connection and emission;
- file read/write snippets with temporary paths;
- exception mapping.

Poor doctest examples:

- object finalization timing;
- platform-specific permission failures;
- large GTK widgets;
- multithreaded closure behavior;
- implementation internals that should stay free to change.

## Focused Tests To Keep

The detailed contracts should live in normal tests:

- namespace isolation;
- generated stub parsing;
- invoke marshalling;
- shared namespace conflict rules;
- signal owner inference and rejection;
- closure inventory;
- async finish pairing;
- `GError` mapping;
- property binding transform lifetime.

The doctest story should fail when the public narrative breaks. The focused
tests should fail when the runtime contract breaks.

Next: [[10 typing by default]]
