#!/usr/bin/env python3

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Drive `inventory_probe.py` once per installed typelib, capture each
JSON result to disk, and summarize.

Per-namespace isolation means one slow or crashing typelib only kills its
own subprocess. Use `--summarize-only` to re-render the report from a
previously collected directory without re-probing.

    PYTHONPATH=build/cpython-3.14t/src \\
        .venv-cpython-3.14t/bin/python3 scripts/inventory_sweep.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

os.environ.setdefault("PYTHON_GIL", "0")

from ginext import private


_QUALIFIED_PREFIX = re.compile(r"^[A-Za-z_][\w.]*:\s*")


def normalize_reason(message: str) -> str:
    return _QUALIFIED_PREFIX.sub("", message).strip()


@dataclass
class ReasonBucket:
    reason: str
    callables: list[str] = field(default_factory=list)
    kinds: dict[str, int] = field(default_factory=lambda: defaultdict(int))


def run_probe(
    probe_path: Path,
    namespace: str,
    version: str,
    out_path: Path,
    timeout: float,
) -> dict[str, Any]:
    cmd = [sys.executable, str(probe_path), namespace, version]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        result = {
            "namespace": namespace,
            "version": version,
            "load_error": f"TIMEOUT after {timeout:.0f}s",
            "built": 0,
            "rejected": 0,
            "errored": 0,
            "total": 0,
            "elapsed_seconds": elapsed,
            "rejections": [],
            "unexpected": [],
        }
        out_path.write_text(json.dumps(result))
        return result

    elapsed = time.monotonic() - started
    stdout = proc.stdout.strip()
    if proc.returncode != 0 and not stdout:
        result = {
            "namespace": namespace,
            "version": version,
            "load_error": (
                f"probe exit={proc.returncode}; stderr={proc.stderr.strip()[:400]}"
            ),
            "built": 0,
            "rejected": 0,
            "errored": 0,
            "total": 0,
            "elapsed_seconds": elapsed,
            "rejections": [],
            "unexpected": [],
        }
        out_path.write_text(json.dumps(result))
        return result

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError as exc:
        result = {
            "namespace": namespace,
            "version": version,
            "load_error": f"bad JSON from probe: {exc}",
            "built": 0,
            "rejected": 0,
            "errored": 0,
            "total": 0,
            "elapsed_seconds": elapsed,
            "rejections": [],
            "unexpected": [],
        }
    out_path.write_text(json.dumps(result))
    return result


def load_results(out_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(out_dir.glob("*.json")):
        try:
            results.append(json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"warning: failed to load {path}: {exc}", file=sys.stderr)
    return results


def collect_reasons(
    results: list[dict[str, Any]],
) -> tuple[dict[str, ReasonBucket], list[dict[str, Any]]]:
    reasons: dict[str, ReasonBucket] = {}
    unexpected: list[dict[str, Any]] = []
    for result in results:
        for rejection in result.get("rejections", ()):
            reason = normalize_reason(rejection["reason"])
            bucket = reasons.get(reason)
            if bucket is None:
                bucket = ReasonBucket(reason=reason)
                reasons[reason] = bucket
            bucket.callables.append(rejection["qualified"])
            bucket.kinds[rejection["kind"]] += 1
        for unexpected_entry in result.get("unexpected", ()):
            unexpected.append({**unexpected_entry, "namespace": result["namespace"]})
    return reasons, unexpected


def print_load_failures(results: list[dict[str, Any]]) -> None:
    failed = [r for r in results if r.get("load_error")]
    if not failed:
        return
    print()
    print("=" * 72)
    print(f"Namespaces that failed to probe ({len(failed)} total)")
    print("=" * 72)
    for r in sorted(failed, key=lambda x: x["namespace"].lower()):
        print(f"  {r['namespace']}/{r['version']}: {r['load_error']}")


def print_slowest(results: list[dict[str, Any]], *, limit: int) -> None:
    timed = [r for r in results if r.get("elapsed_seconds", 0) > 0]
    if not timed:
        return
    timed.sort(key=lambda x: x["elapsed_seconds"], reverse=True)
    print()
    print("=" * 72)
    print(f"Slowest namespaces (top {min(limit, len(timed))})")
    print("=" * 72)
    for r in timed[:limit]:
        print(
            f"  {r['namespace']:<28} {r['version']:<8} "
            f"{r['elapsed_seconds']:>7.2f}s   total={r.get('total', 0)}"
        )


def print_reasons(reasons: dict[str, ReasonBucket], *, top: int, samples: int) -> None:
    if not reasons:
        print("No NotImplementedError reasons collected.")
        return
    ordered = sorted(reasons.values(), key=lambda b: len(b.callables), reverse=True)
    total_rejected = sum(len(b.callables) for b in ordered)
    print()
    print("=" * 72)
    print(
        f"Top {min(top, len(ordered))} unsupported-signature reasons "
        f"({total_rejected} rejected callables across {len(ordered)} reasons)"
    )
    print("=" * 72)
    for rank, bucket in enumerate(ordered[:top], start=1):
        count = len(bucket.callables)
        kind_summary = ", ".join(
            f"{kind}={n}" for kind, n in sorted(bucket.kinds.items())
        )
        print()
        print(f"[{rank:>2}] {count:>5} callables  ({kind_summary})")
        print(f"     reason: {bucket.reason}")
        for qualified in bucket.callables[:samples]:
            print(f"       - {qualified}")
        if count > samples:
            print(f"       ... and {count - samples} more")


def print_per_namespace(
    results: list[dict[str, Any]],
    *,
    only: set[str] | None,
    samples: int,
    skip_empty: bool,
) -> None:
    selected = [
        r
        for r in results
        if (only is None or r["namespace"] in only)
        and not r.get("load_error")
        and (not skip_empty or r.get("rejected", 0) > 0)
    ]
    if not selected:
        return
    selected.sort(key=lambda r: r["namespace"].lower())
    print()
    print("=" * 72)
    print(f"Per-namespace rejection detail ({len(selected)} namespaces)")
    print("=" * 72)
    for r in selected:
        rejections = r.get("rejections", [])
        per_reason: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for entry in rejections:
            reason = normalize_reason(entry["reason"])
            per_reason[reason].append((entry["qualified"], entry["kind"]))
        ordered = sorted(per_reason.items(), key=lambda kv: len(kv[1]), reverse=True)
        print()
        print(
            f"{r['namespace']}/{r['version']}: "
            f"built={r.get('built', 0)}  rejected={r.get('rejected', 0)}  "
            f"errored={r.get('errored', 0)}  total={r.get('total', 0)}"
        )
        for reason, entries in ordered:
            kinds: dict[str, int] = defaultdict(int)
            for _, kind in entries:
                kinds[kind] += 1
            kind_str = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
            print(f"  - {len(entries):>3} ({kind_str})  {reason}")
            for qualified, _kind in entries[:samples]:
                print(f"      * {qualified}")
            if len(entries) > samples:
                print(f"      ... and {len(entries) - samples} more")


def print_unexpected(unexpected: list[dict[str, Any]], *, limit: int) -> None:
    if not unexpected:
        return
    print()
    print("=" * 72)
    print(f"Unexpected exceptions ({len(unexpected)} total)")
    print("=" * 72)
    for entry in unexpected[:limit]:
        print(
            f"  [{entry['namespace']}/{entry['kind']}] "
            f"{entry['qualified']}: {entry['exc_type']}: {entry['message']}"
        )
    if len(unexpected) > limit:
        print(f"  ... and {len(unexpected) - limit} more")


def print_totals(
    results: list[dict[str, Any]], reasons: dict[str, ReasonBucket]
) -> None:
    loaded = [r for r in results if not r.get("load_error")]
    built = sum(r.get("built", 0) for r in loaded)
    rejected = sum(r.get("rejected", 0) for r in loaded)
    errored = sum(r.get("errored", 0) for r in loaded)
    total = sum(r.get("total", 0) for r in loaded)
    elapsed = sum(r.get("elapsed_seconds", 0.0) for r in results)
    print()
    print("=" * 72)
    print("Totals")
    print("=" * 72)
    print(f"  namespaces probed: {len(loaded)} / {len(results)} attempted")
    print(f"  reasons (unique):  {len(reasons)}")
    print(f"  total elapsed:     {elapsed:.1f}s")
    if total:
        pct = 100.0 * built / total
        print(f"  callables probed: {total}")
        print(
            f"  built:    {built:>6} ({pct:5.1f}%)\n"
            f"  rejected: {rejected:>6} ({100.0 * rejected / total:5.1f}%)\n"
            f"  errored:  {errored:>6} ({100.0 * errored / total:5.1f}%)"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default="/tmp/ginext-inventory",
        type=Path,
        help="Where to store one JSON file per namespace (default: /tmp/ginext-inventory).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-namespace timeout in seconds (default: 60).",
    )
    parser.add_argument(
        "--namespace",
        action="append",
        default=None,
        help="Only probe the given namespace(s). May be repeated.",
    )
    parser.add_argument(
        "--summarize-only",
        action="store_true",
        help="Skip probing, just re-read out-dir and print the report.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="How many reason buckets to show (default: 25).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=8,
        help="Sample callables per reason bucket (default: 8).",
    )
    parser.add_argument(
        "--unexpected-limit",
        type=int,
        default=50,
        help="Cap on unexpected exceptions to print (default: 50).",
    )
    parser.add_argument(
        "--slowest",
        type=int,
        default=15,
        help="Show this many slowest namespaces (default: 15).",
    )
    parser.add_argument(
        "--per-namespace",
        action="store_true",
        help=(
            "Print one section per namespace listing its rejections grouped "
            "by reason. Combine with --ns to limit which namespaces."
        ),
    )
    parser.add_argument(
        "--ns",
        action="append",
        default=None,
        metavar="NAME",
        help=(
            "Limit --per-namespace output to these namespaces. May be repeated. "
            "Default: every namespace with at least one rejection."
        ),
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="In --per-namespace, also list namespaces with zero rejections.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    probe_path = Path(__file__).resolve().parent / "inventory_probe.py"

    if not args.summarize_only:
        installed = private.installed_versions()
        if args.namespace:
            wanted: list[tuple[str, str]] = []
            for ns in args.namespace:
                if ns not in installed:
                    print(
                        f"warning: {ns} not in installed_versions()",
                        file=sys.stderr,
                    )
                    continue
                wanted.append((ns, installed[ns][0]))
        else:
            wanted = sorted(
                ((ns, vers[0]) for ns, vers in installed.items()),
                key=lambda nv: nv[0].lower(),
            )

        for index, (ns, ver) in enumerate(wanted, start=1):
            out_path = args.out_dir / f"{ns}.json"
            start = time.monotonic()
            result = run_probe(probe_path, ns, ver, out_path, args.timeout)
            elapsed = time.monotonic() - start
            status = (
                "LOAD-FAIL"
                if result.get("load_error")
                else f"built={result['built']} rej={result['rejected']}"
            )
            print(
                f"[{index:>3}/{len(wanted)}] {ns:<32} {ver:<8} "
                f"{elapsed:6.2f}s  {status}",
                flush=True,
            )

    results = load_results(args.out_dir)
    reasons, unexpected = collect_reasons(results)
    print_slowest(results, limit=args.slowest)
    print_load_failures(results)
    print_reasons(reasons, top=args.top, samples=args.samples)
    if args.per_namespace:
        only = set(args.ns) if args.ns else None
        print_per_namespace(
            results,
            only=only,
            samples=args.samples,
            skip_empty=not args.include_empty,
        )
    print_unexpected(unexpected, limit=args.unexpected_limit)
    print_totals(results, reasons)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
