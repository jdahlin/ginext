"""
Shared bootstrap for the draw-bench scripts.

Each bench script runs in *one* of three modes — `jit`, `ffi`, or `gi` —
because goi's call-mode is process-global and goi+gi can't both own
the canonical GoiBench import.

Use `setup_backend()` from a bench script's top level: it parses
`--backend=` from sys.argv, re-execs once to seed LD_LIBRARY_PATH /
GI_TYPELIB_PATH if needed, sets goi's call_mode when applicable, and
returns the imported `GoiBench` namespace plus the backend label.

For the multi-backend driver pattern, see `microbench.py`'s top-level
subprocess loop or `run_all.py`.

NOTE on `--backend=gi`: this expects *real* PyGObject (system
`/usr/lib/python3/dist-packages/gi`), not goi's gi-compat shim. We
filter goi's build dir out of sys.path for the gi case, so you need
PyGObject importable from the venv's interpreter or it errors with
ModuleNotFoundError. Install with e.g. `apt install python3-gi` and
use a venv that inherits system site-packages, or install PyGObject
into the venv directly.
"""

from __future__ import annotations

import os
import pathlib
import sys

BACKENDS = ("jit", "ffi", "gi")

_HERE = pathlib.Path(__file__).resolve().parent.parent.parent


def _seed_typelib_env() -> None:
    builds_root = _HERE / "build"
    candidates = []
    if builds_root.is_dir():
        candidates = [
            d / "packages" / "typelib"
            for d in builds_root.iterdir()
            if d.is_dir()
        ]
    # Pick the most recently built typelib so a fresh `ninja -C build/X`
    # is always preferred over a stale older build dir.
    fresh = sorted(
        [p for p in candidates if (p / "GoiBench-1.0.typelib").exists()],
        key=lambda p: (p / "GoiBench-1.0.typelib").stat().st_mtime,
        reverse=True,
    )
    for p in fresh:
        if str(p) in os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep):
            return
        sep = os.pathsep
        old_ld = os.environ.get("LD_LIBRARY_PATH", "")
        old_tl = os.environ.get("GI_TYPELIB_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = str(p) + (sep + old_ld if old_ld else "")
        os.environ["GI_TYPELIB_PATH"] = str(p) + (sep + old_tl if old_tl else "")
        os.execvp(sys.executable, [sys.executable, *sys.argv])


def parse_backend(argv: list[str]) -> str | None:
    if "--gi" in argv:
        argv.remove("--gi")
        return "gi"
    for i, a in enumerate(argv):
        if a == "--backend" and i + 1 < len(argv):
            v = argv.pop(i + 1)
            argv.pop(i)
            return v
        if a.startswith("--backend="):
            argv.pop(i)
            return a.split("=", 1)[1]
    return None


def setup_backend():
    """Returns (GoiBench_module, backend_label) or raises SystemExit."""
    _seed_typelib_env()
    backend = parse_backend(sys.argv)
    if backend is None:
        sys.exit("pass --backend=jit|ffi|gi (or run via the multi-backend driver)")
    if backend not in BACKENDS:
        sys.exit(f"unknown backend {backend!r}; expected {BACKENDS}")
    if backend == "gi":
        # Make sure we resolve real PyGObject, not goi's gi-compat shim.
        # The shim sits next to the `goi.cpython-*.so` extension on PYTHONPATH;
        # drop every sys.path entry that ships its own `goi` extension.
        import glob
        import os

        def _has_gir_ext(p: str) -> bool:
            return bool(p) and bool(glob.glob(os.path.join(p, "_goi*.so")))

        sys.path = [p for p in sys.path if not _has_gir_ext(p)]
        for mod in [m for m in sys.modules if m == "gi" or m.startswith("gi.")]:
            del sys.modules[mod]
        try:
            import gi
        except ModuleNotFoundError:
            print(
                "  SKIP: real PyGObject not importable from this interpreter "
                "(install python3-gi or pip install PyGObject in the venv)"
            )
            sys.exit(0)
        # Detect the shim by reading its banner — robust against arbitrary
        # paths (the venv itself may sit under a "goi" parent directory).
        try:
            with open(gi.__file__, "r") as f:
                head = f.read(200)
        except OSError:
            head = ""
        if "goi's pygobject-API compatibility shim" in head:
            sys.exit(
                f"--backend=gi resolved to goi's compat shim ({gi.__file__}); "
                f"set PYTHONPATH so real PyGObject wins"
            )
        gi.require_version("GoiBench", "1.0")
        from gi.repository import GoiBench
    else:
        from goi import _goi

        _goi.require_version("GoiBench", "1.0")
        _goi.set_call_mode(backend)
        GoiBench = _goi.open_namespace("GoiBench", "1.0")
    return GoiBench, backend


def header(title: str, backend: str) -> None:
    py = f"py{sys.version_info.major}.{sys.version_info.minor}"
    print(f"=== {title} [{backend} {py}] ===")


def bench(name: str, fn, n: int = 5_000_000) -> None:
    import time

    for _ in range(min(n // 100, 50_000)):
        fn()
    t = time.perf_counter()
    for _ in range(n):
        fn()
    dt = time.perf_counter() - t
    ns = dt * 1e9 / n
    rate = n / dt
    print(f"  {name:<36}  {ns:7.1f} ns/call   {rate / 1e6:6.2f} M/s")


def bench_inner(name: str, fn, outer: int, inner: int) -> None:
    import time

    for _ in range(min(outer // 10, 10_000)):
        fn()
    t = time.perf_counter()
    for _ in range(outer):
        fn()
    dt = time.perf_counter() - t
    calls = outer * inner
    ns = dt * 1e9 / calls
    rate = calls / dt
    print(f"  {name:<36}  {ns:7.1f} ns/call   {rate / 1e6:6.2f} M/s")
