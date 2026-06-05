#!/usr/bin/env python3
"""Read GSettings with ginext's Gio.Settings.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/gio/settings.py [SCHEMA_ID]

Picks the first installed schema from a small candidate list (or the one given
on the command line) and prints its keys. ginext's Gio.Settings overlay makes a
settings object behave like a read-only mapping: `len`, `in`, iteration over
keys, and `settings[key]` returning the unpacked value.
"""

from __future__ import annotations

import sys

from ginext import Gio

CANDIDATES = [
    "org.gtk.Settings.FileChooser",
    "org.gtk.Settings.Debug",
    "org.gnome.desktop.interface",
]


def is_installed(schema_id: str) -> bool:
    source = Gio.SettingsSchemaSource.get_default()
    return source is not None and source.lookup(schema_id, True) is not None


def main() -> int:
    candidates = sys.argv[1:] or CANDIDATES
    schema_id = next((s for s in candidates if is_installed(s)), None)
    if schema_id is None:
        print("none of these schemas are installed:")
        for s in candidates:
            print(f"  {s}")
        return 0

    settings = Gio.Settings.new(schema_id)
    print(f"schema: {schema_id}  ({len(settings)} keys)")
    for key in settings:
        print(f"  {key} = {settings[key]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
