#!/usr/bin/env python3
# Single source of truth for the workspace version.
#
# Rewrites the version in meson.build, every pyproject.toml [project].version,
# and the inter-package dependency pins (ginext>=X, ginext-gio>=X, ...) so a
# release of the native core and its overlays always move together. The release
# workflow (.github/workflows/release.yml) asserts the pushed tag matches what
# `--check` reports here, so this file is the canonical version.
#
#   python scripts/bump_version.py 0.8.0   # rewrite everything to 0.8.0
#   python scripts/bump_version.py --check # print the current version, exit 0
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The workspace packages whose >=X pins are rewritten together. `gi` is the core
# distribution name (the importable package is still `ginext`).
PINNED_NAMES = [
    "ginext-core",
    "ginext-gio",
    "ginext-gtk",
    "ginext-gst",
    "ginext-libsoup",
    "ginext-gi-compat",
    "ginext-stubgen",
    "ginext-stubs",
]

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[._-]?(?:a|b|rc|dev|post)\d+)?$")


def pyproject_files() -> list[pathlib.Path]:
    return [ROOT / "pyproject.toml", *sorted(ROOT.glob("packages/*/pyproject.toml"))]


def current_version() -> str:
    text = (ROOT / "meson.build").read_text(encoding="utf-8")
    m = re.search(r"version\s*:\s*'([^']+)'", text)
    if not m:
        raise SystemExit("could not find version in meson.build")
    return m.group(1)


def bump(version: str) -> list[pathlib.Path]:
    changed: list[pathlib.Path] = []

    # meson.build: project(... version : '...' ...)
    meson = ROOT / "meson.build"
    text = meson.read_text(encoding="utf-8")
    new = re.sub(r"(version\s*:\s*')[^']+(')", rf"\g<1>{version}\g<2>", text, count=1)
    if new != text:
        meson.write_text(new, encoding="utf-8")
        changed.append(meson)

    # Longest names first so `gi` never shadows `ginext-gio` etc. in the
    # alternation (the trailing `>=` guard already prevents a false match, but
    # ordering keeps it obvious).
    pin_alt = "|".join(
        re.escape(n) for n in sorted(PINNED_NAMES, key=len, reverse=True)
    )
    # `ginext-gio>=0.0.1` inside a dependency string, with optional extras/quote.
    pin_re = re.compile(rf'("(?:{pin_alt}))(\[[^\]]*\])?>=[^"\s,]+')

    for pp in pyproject_files():
        text = pp.read_text(encoding="utf-8")
        new = re.sub(
            r'(?m)^(version\s*=\s*")[^"]+(")', rf"\g<1>{version}\g<2>", text, count=1
        )
        new = pin_re.sub(rf"\g<1>\g<2>>={version}", new)
        if new != text:
            pp.write_text(new, encoding="utf-8")
            changed.append(pp)

    return changed


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    if argv[0] in ("--check", "-c"):
        print(current_version())
        return 0
    version = argv[0]
    if not VERSION_RE.match(version):
        raise SystemExit(f"not a valid version: {version!r}")
    changed = bump(version)
    for p in changed:
        print(f"updated {p.relative_to(ROOT)}")
    print(f"version -> {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
