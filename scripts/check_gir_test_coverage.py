#!/usr/bin/env python3
from __future__ import annotations

import argparse
import pathlib
import sys

from goi.tests.gir_coverage import analyze_namespace
from goi.tests.gir_coverage import default_gir_dir
from goi.tests.gir_coverage import parse_gir_functions
from goi.tests.gir_coverage import repo_root


def check_namespace(gir_path: pathlib.Path, tests_dir: pathlib.Path) -> int:
    result = analyze_namespace(gir_path, tests_dir)
    namespace = result["namespace"]
    gir_functions = result["gir_functions"]
    test_path = result["test_path"]
    covered = result["covered"]
    missing = result["missing"]
    calls_by_test = result["calls_by_test"]

    print(f"[{namespace}] {gir_path.name}")
    if not result["test_exists"]:
        print(f"  test module: missing ({test_path.relative_to(repo_root())})")
        print(f"  uncovered: {len(gir_functions)}/{len(gir_functions)}")
        return 1

    print(f"  test module: {test_path.relative_to(repo_root())}")
    print(f"  tests: {len(calls_by_test)}")
    print(f"  covered: {len(covered)}/{len(gir_functions)}")

    if missing:
        for name in missing:
            print(f"    MISSING {name}")
        return 1

    return 0


def main(argv: list[str]) -> int:
    root = repo_root()
    parser = argparse.ArgumentParser(
        description=(
            "Parse built .gir XML files and check whether each top-level GIR "
            "function appears in the matching manual pytest module."
        )
    )
    parser.add_argument(
        "--gir-dir",
        type=pathlib.Path,
        default=default_gir_dir(root),
        help="Directory containing built .gir files.",
    )
    parser.add_argument(
        "--tests-dir",
        type=pathlib.Path,
        default=root / "tests",
        help="Directory containing manual pytest modules.",
    )
    parser.add_argument(
        "namespaces",
        nargs="*",
        help="Optional namespace filter, e.g. Regress GIMarshallingTests",
    )
    args = parser.parse_args(argv)

    gir_paths = sorted(args.gir_dir.glob("*.gir"))
    if not gir_paths:
        print(f"no .gir files found in {args.gir_dir}", file=sys.stderr)
        return 2

    wanted = set(args.namespaces)
    status = 0
    for gir_path in gir_paths:
        namespace, _ = parse_gir_functions(gir_path)
        if wanted and namespace not in wanted:
            continue
        status |= check_namespace(gir_path, args.tests_dir)

    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
