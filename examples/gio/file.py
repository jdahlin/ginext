#!/usr/bin/env python3
"""Gio.File basics with ginext.

Run via:
    PYTHONPATH=build/cpython-3.14t/src \\
      .venv-cpython-3.14t/bin/python3 examples/gio/file.py

Shows path/uri helpers, query_info with default flags, the blocking read, and
a Gio.Cancellable used as a cancel scope.
"""

from __future__ import annotations

import tempfile

from ginext import Gio


def main() -> int:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"hello from ginext\n")
        path = tmp.name

    file = Gio.File.new_for_path(path)

    # Pathlib-ish helpers.
    print("uri:        ", file.get_uri())
    print("basename:   ", file.get_basename())
    print("parent:     ", file.get_parent().get_path())
    print("child a/b:  ", (file.get_parent() / "a" / "b").get_path())

    # query_info: flags defaults to NONE, cancellable is omittable.
    info = file.query_info("standard::name,standard::size")
    print("name:       ", info.get_name())
    print("size:       ", info.get_size())

    # Blocking read (cancellable is omittable).
    ok, data, _etag = file.load_contents()
    print("sync read:  ", bytes(data))

    # A Gio.Cancellable is a cancel scope: it is the current cancellable inside
    # the block and is cancelled on exit, so work tied to it stops.
    with Gio.Cancellable() as cancel:
        file.query_info("standard::name", Gio.FileQueryInfoFlags.NONE, cancel)
        print("in scope:   ", "cancelled" if cancel.is_cancelled() else "live")
    print("after scope:", "cancelled" if cancel.is_cancelled() else "live")

    file.delete()  # cancellable omittable
    print("deleted:    ", not file.query_exists())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
