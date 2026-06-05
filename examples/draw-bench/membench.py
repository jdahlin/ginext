"""
membench — RSS memory footprint and import latency after namespace import.

Measures how much physical memory (RSS) and wall time importing a namespace
costs, comparing goi (lazy) vs real PyGObject (eager).

Usage:
    python membench.py                              # all backends, all namespaces
    python membench.py --namespace=Gtk              # one namespace, all backends
    python membench.py --backend=goi              # all namespaces, one backend

Internal subprocess mode (not for direct use):
    python membench.py --backend=goi --namespace=Gtk:4.0
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

_HERE = pathlib.Path(__file__).resolve().parent.parent.parent

BACKENDS = ("goi", "gi")

NAMESPACES = [
    ("GLib", "2.0"),
    ("GObject", "2.0"),
    ("Gio", "2.0"),
    ("Gtk", "4.0"),
    ("Gst", "1.0"),
]


# ---------------------------------------------------------------------------
# Subprocess mode — runs when both --backend and --namespace are given.
# Prints: "<rss_before_kb> <rss_after_kb> <elapsed_ms>" or "SKIP <reason>".
# ---------------------------------------------------------------------------


def _rss_kb() -> int:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        pass
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _suppress_editable_rebuild() -> None:
    """Prevent meson-python's editable finder from triggering a rebuild.
    Instead wire up the build's src/ directory on sys.path directly so
    `import goi` and `import _goi` resolve without the finder."""
    import glob as _glob

    for finder in sys.meta_path:
        if type(finder).__name__ != "MesonpyMetaFinder":
            continue
        build_path = getattr(finder, "_build_path", None)
        if not build_path:
            break
        existing = os.environ.get("MESONPY_EDITABLE_SKIP", "")
        if str(build_path) not in existing.split(os.pathsep):
            os.environ["MESONPY_EDITABLE_SKIP"] = (
                f"{existing}{os.pathsep}{build_path}" if existing else str(build_path)
            )
        # Also add the src/ dir containing the built extension + goi package.
        src_dir = os.path.join(build_path, "src")
        if os.path.isdir(src_dir) and _glob.glob(os.path.join(src_dir, "_goi*.so")):
            if src_dir not in sys.path:
                sys.path.insert(0, src_dir)
        break


def _subprocess_measure(backend: str, ns_name: str, ns_version: str) -> None:
    import gc
    import time

    gc.collect()
    before = _rss_kb()
    t0 = time.perf_counter()

    try:
        if backend == "goi":
            _suppress_editable_rebuild()
            sys.path.insert(0, str(_HERE / "src" / "gi_compat"))
            # If editable suppress didn't find the .so, fall back to manual search.
            import glob as _glob

            if not any(_glob.glob(os.path.join(p, "_goi*.so")) for p in sys.path):
                builds = sorted(
                    (_HERE / "build").iterdir(),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                for b in builds:
                    ext_dir = b / "src"
                    if any(ext_dir.glob("_goi*.so")):
                        sys.path.insert(0, str(ext_dir))
                        break
            import gi

            gi.require_version(ns_name, ns_version)
            mod = __import__("gi.repository", fromlist=[ns_name])
            getattr(mod, ns_name)
        else:
            # Real PyGObject — strip goi paths from sys.path
            import glob as _glob

            sys.path = [
                p
                for p in sys.path
                if not _glob.glob(os.path.join(p, "_goi*.so"))
                and not _glob.glob(os.path.join(p, "goi*.so"))
            ]
            import gi

            gi.require_version(ns_name, ns_version)
            mod = __import__("gi.repository", fromlist=[ns_name])
            getattr(mod, ns_name)
    except Exception as e:
        print(f"SKIP {e}")
        return

    elapsed_ms = (time.perf_counter() - t0) * 1000
    after = _rss_kb()
    print(f"{before} {after} {elapsed_ms:.1f}")


# ---------------------------------------------------------------------------
# Driver — spawns one subprocess per (backend, namespace) cell.
# ---------------------------------------------------------------------------


def _run_cell(
    backend: str, ns_name: str, ns_version: str
) -> tuple[int, int, float] | str:
    """Returns (before_kb, after_kb, elapsed_ms) or a skip/error string."""
    cmd = [
        sys.executable,
        str(_HERE / "examples/draw-bench/membench.py"),
        f"--backend={backend}",
        f"--namespace={ns_name}:{ns_version}",
    ]
    env = os.environ.copy()
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = (r.stdout + r.stderr).strip()
    if not out:
        return "err"
    first = out.splitlines()[0]
    if first.startswith("SKIP"):
        return first
    try:
        before, after, ms = first.split()
        return int(before), int(after), float(ms)
    except ValueError:
        return "err"


def _mib(kb: int) -> str:
    return f"{kb / 1024:.1f} MiB"


def main() -> None:
    namespaces = NAMESPACES
    backends = BACKENDS

    # Parse optional filters
    args = sys.argv[1:]
    ns_filter = next(
        (a.split("=", 1)[1] for a in args if a.startswith("--namespace=")), None
    )
    be_filter = next(
        (a.split("=", 1)[1] for a in args if a.startswith("--backend=")), None
    )
    if ns_filter:
        namespaces = [(n, v) for n, v in namespaces if n == ns_filter]
    if be_filter:
        backends = [be_filter]

    results: dict[tuple[str, str], dict[str, tuple[int, int, float] | str]] = {}
    for ns_name, ns_version in namespaces:
        key = (ns_name, ns_version)
        results[key] = {}
        for backend in backends:
            cell = _run_cell(backend, ns_name, ns_version)
            results[key][backend] = cell
            status = "skip" if isinstance(cell, str) else f"+{_mib(cell[1] - cell[0])}"
            print(f"  {backend:6}  {ns_name}-{ns_version}  {status}", flush=True)

    # Print table
    ns_w = max(len(f"{n}-{v}") for n, v in namespaces)
    col_w = 14
    print()
    print("=" * (ns_w + 4 + col_w * len(backends) * 2))
    header = f"  {'namespace':<{ns_w}}"
    for b in backends:
        header += f"  {(b + ' RSS'):>{col_w}}  {(b + ' time'):>{col_w}}"
    print(header)
    print("-" * len(header))

    for (ns_name, ns_version), cells in results.items():
        row = f"  {ns_name + '-' + ns_version:<{ns_w}}"
        for b in backends:
            cell = cells.get(b, "err")
            if isinstance(cell, str):
                row += f"  {'—':>{col_w}}  {'—':>{col_w}}"
            else:
                before, after, ms = cell
                delta = after - before
                row += f"  {_mib(delta):>{col_w}}  {f'{ms:.0f} ms':>{col_w}}"
        print(row)


# ---------------------------------------------------------------------------
# Entry point — subprocess mode or driver mode.
# ---------------------------------------------------------------------------

_args = sys.argv[1:]
_backend = next((a.split("=", 1)[1] for a in _args if a.startswith("--backend=")), None)
_ns_arg = next(
    (a.split("=", 1)[1] for a in _args if a.startswith("--namespace=")), None
)

if _backend and _ns_arg and ":" in _ns_arg:
    # Subprocess mode
    _ns_name, _ns_version = _ns_arg.split(":", 1)
    _subprocess_measure(_backend, _ns_name, _ns_version)
else:
    main()
