#!/usr/bin/env python3

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Regenerate the committed snapshot of "unsupported argument type"
rejections used by ``tests/inventory/test_unsupported_argument_args.py``.

Reads ``/tmp/ginext-inventory/*.json`` (the per-namespace probe output
from ``inventory_sweep.py``) and writes
``src/ginext/tests/inventory/_unsupported_argument_args.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_TARGET_REASON_RE = re.compile(
    r"^unsupported argument type(?:\s*\[[^]]*\])? is outside the current "
    r"ginext invoke slice$"
)
_QUALIFIED_PREFIX = re.compile(r"^[A-Za-z_][\w.]*:\s*")
_GIR_DIR = Path("/usr/share/gir-1.0")
_GTK3_INCLUDE_RE = re.compile(
    r'<include name="(?:Gtk|Gdk|GdkX11|GdkWayland)" version="3\.0"'
    r'|shared-library="[^"]*gtk-3'
)


def normalize_reason(message: str) -> str:
    return _QUALIFIED_PREFIX.sub("", message).strip()


def gtk3_gir_dependencies() -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = {("Gtk", "3.0"), ("Gdk", "3.0")}
    if not _GIR_DIR.is_dir():
        return result
    for path in _GIR_DIR.glob("*.gir"):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        if not _GTK3_INCLUDE_RE.search(text):
            continue
        stem = path.stem
        if "-" not in stem:
            continue
        namespace, version = stem.rsplit("-", 1)
        result.add((namespace, version))
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory-dir",
        default=Path("/tmp/ginext-inventory"),
        type=Path,
        help="Directory of per-namespace JSON output from inventory_sweep.py.",
    )
    parser.add_argument(
        "--out",
        default=Path("src/ginext/tests/inventory/_unsupported_argument_args.json"),
        type=Path,
        help="Path to the JSON snapshot.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    gtk3_deps = gtk3_gir_dependencies()
    # Preserve any "skip_reason" annotations from the existing snapshot
    # so regenerations don't clobber manually-curated entries.
    prior_skips: dict[str, str] = {}
    if args.out.exists():
        try:
            for prior in json.loads(args.out.read_text()):
                if prior.get("skip_reason"):
                    prior_skips[prior["qualified"]] = prior["skip_reason"]
        except (OSError, json.JSONDecodeError):
            pass
    entries: list[dict[str, Any]] = []
    for jpath in sorted(args.inventory_dir.glob("*.json")):
        data = json.loads(jpath.read_text())
        namespace = data["namespace"]
        version = data.get("version", "")
        is_gtk3 = (namespace, version) in gtk3_deps
        for rejection in data.get("rejections", ()):
            if not _TARGET_REASON_RE.match(normalize_reason(rejection["reason"])):
                continue
            entry = {
                "namespace": namespace,
                "version": version,
                "qualified": rejection["qualified"],
                "kind": rejection["kind"],
                "is_gtk3": is_gtk3,
            }
            if rejection["qualified"] in prior_skips:
                entry["skip_reason"] = prior_skips[rejection["qualified"]]
            entries.append(entry)
    entries.sort(key=lambda e: (e["namespace"].lower(), e["qualified"]))
    args.out.write_text(json.dumps(entries, indent=2) + "\n")
    print(f"wrote {len(entries)} entries to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
