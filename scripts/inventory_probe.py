#!/usr/bin/env python3

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Probe one installed typelib: try `build_callable_descriptor` on every
callable signature we can reach (top-level functions, object methods,
record/union methods) and emit a JSON document on stdout describing what
built cleanly, what was rejected (with reason), and what raised
unexpectedly.

Intended to be spawned one-per-namespace by `inventory_sweep.py` so a
slow or crashing typelib never blocks the rest of the sweep.

    python scripts/inventory_probe.py GLib 2.0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from typing import Any, Iterator

os.environ.setdefault("PYTHON_GIL", "0")

from ginext import private


def iter_callables(namespace: str, version: str) -> Iterator[tuple[str, str, object]]:
    for member_name in private.namespace_dir(namespace, version):
        try:
            kind, info = private.namespace_find(namespace, version, member_name)
        except Exception:
            continue

        if kind == "function":
            try:
                py_name = private.callable_name(info).replace("-", "_")
            except Exception:
                py_name = member_name
            yield f"{namespace}.{py_name}", "function", info
            continue

        if kind == "object":
            try:
                data = private.object_info(info)
            except Exception:
                continue
            for method_info in data.get("methods", ()):
                try:
                    name = private.callable_name(method_info).replace("-", "_")
                except Exception:
                    continue
                yield (
                    f"{namespace}.{member_name}.{name}",
                    "object-method",
                    method_info,
                )
            continue

        if kind in ("record", "union"):
            try:
                data = private.record_info(info)
            except Exception:
                continue
            kind_label = "record-method" if kind == "record" else "union-method"
            for method_info in data.get("methods", ()):
                try:
                    name = private.callable_name(method_info).replace("-", "_")
                except Exception:
                    continue
                yield (
                    f"{namespace}.{member_name}.{name}",
                    kind_label,
                    method_info,
                )


def probe(namespace: str, version: str) -> dict[str, Any]:
    started = time.monotonic()
    result: dict[str, Any] = {
        "namespace": namespace,
        "version": version,
        "load_error": None,
        "built": 0,
        "rejected": 0,
        "errored": 0,
        "total": 0,
        "elapsed_seconds": 0.0,
        "rejections": [],
        "unexpected": [],
    }

    try:
        private.require_namespace(namespace, version)
    except Exception as exc:
        result["load_error"] = f"{type(exc).__name__}: {exc}"
        result["elapsed_seconds"] = time.monotonic() - started
        return result

    for qualified, kind, info in iter_callables(namespace, version):
        result["total"] += 1
        try:
            has_self = private.callable_has_self(info) if kind != "function" else False
        except Exception:
            has_self = kind != "function"

        try:
            private.build_callable_descriptor(info, qualified, has_self)
        except NotImplementedError as exc:
            result["rejected"] += 1
            result["rejections"].append(
                {
                    "qualified": qualified,
                    "kind": kind,
                    "reason": str(exc),
                }
            )
        except Exception as exc:
            result["errored"] += 1
            result["unexpected"].append(
                {
                    "qualified": qualified,
                    "kind": kind,
                    "exc_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
        else:
            result["built"] += 1

    result["elapsed_seconds"] = time.monotonic() - started
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("namespace")
    parser.add_argument("version")
    args = parser.parse_args(argv)

    try:
        result = probe(args.namespace, args.version)
    except Exception:
        json.dump(
            {
                "namespace": args.namespace,
                "version": args.version,
                "load_error": "probe crashed",
                "crash_traceback": traceback.format_exc(),
                "built": 0,
                "rejected": 0,
                "errored": 0,
                "total": 0,
                "elapsed_seconds": 0.0,
                "rejections": [],
                "unexpected": [],
            },
            sys.stdout,
        )
        sys.stdout.write("\n")
        return 1

    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
