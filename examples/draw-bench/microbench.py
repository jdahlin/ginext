"""
microbench — full-coverage call/method/property/signal bench across
jit / ffi / gi backends.

Driven against the in-tree GoiBench typelib
(`packages/typelib/`) whose method bodies are all stubs
(return self / return field / no-op), so wall-clock per call ≈ goi or
PyGObject dispatch + marshal cost. Sections:

  free functions     0–6 int args, mixed lanes (free C functions)
  direct callbacks   C loops that invoke Python callbacks with no args,
                     scalar returns, OUT params, mixed lanes, user-data.
  GObject methods    self + bool/utf8/int/GObject — mirrors the trace
                     from running the drawing app: set_enabled,
                     set_label, lookup_action, get_current_page,
                     get_nth_page, page_num.
  property dispatch  get_property('value') / set_property
  signal emit        connect Python lambda to "tick", emit N times,
                     plus a no-listener baseline.

Usage:
    python microbench.py                    # all backends, all sections
    python microbench.py --backend=jit      # one backend (one process)
    python microbench.py --backend=ffi
    python microbench.py --backend=gi       # real PyGObject (system)
    python microbench.py --gi               # legacy alias for --backend=gi

The default (no --backend) re-execs three subprocesses — one per
backend — because goi+gi can't both be the canonical GoiBench at
once and goi's call_mode is process-global.

Real PyGObject for `--backend=gi` must be importable from the
interpreter (e.g. `apt install python3-gi` plus a venv that inherits
system site-packages). Otherwise the gi pass prints SKIP.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

from _bench_common import BACKENDS, setup_backend, header, bench, bench_inner

_HERE = pathlib.Path(__file__).resolve().parent.parent.parent


# Output format from `bench()`:  "  <name padded 36>  <ns> ns/call   <rate> M/s"
_BENCH_LINE = re.compile(
    r"^  (\S.{0,34}\S|\S)\s{2,}([\d.]+)\sns/call\s+([\d.]+)\sM/s\s*$"
)
_SECTION_LINE = re.compile(r"^--- (.+)$")
_HEADER_LINE = re.compile(r"^=== microbench \[(\w+)")


def _run_one(backend: str) -> tuple[bool, list[tuple[str, str, float | None]]]:
    """Run one subprocess; return (ok, [(section, name, ns_or_None), ...])."""
    cmd = [
        sys.executable,
        str(_HERE / "examples/draw-bench/microbench.py"),
        f"--backend={backend}",
    ]
    r = subprocess.run(cmd, env=os.environ.copy(), capture_output=True, text=True)
    rows: list[tuple[str, str, float | None]] = []
    section = ""
    for line in (r.stdout + r.stderr).splitlines():
        m = _SECTION_LINE.match(line)
        if m:
            section = m.group(1)
            continue
        m = _BENCH_LINE.match(line)
        if m:
            rows.append((section, m.group(1).strip(), float(m.group(2))))
            continue
        if "SKIP" in line:
            return (True, rows)  # graceful skip (e.g. PyGObject missing)
    return (r.returncode == 0, rows)


def _collate_and_print(
    per_backend: dict[str, list[tuple[str, str, float | None]]],
) -> None:
    # Preserve the order of sections/rows from whichever backend ran first.
    order: list[tuple[str, str]] = []
    seen = set()
    for backend in BACKENDS:
        for section, name, _ in per_backend.get(backend, []):
            key = (section, name)
            if key not in seen:
                seen.add(key)
                order.append(key)

    by_key: dict[tuple[str, str], dict[str, float]] = {}
    for backend, rows in per_backend.items():
        for section, name, ns in rows:
            if ns is not None:
                by_key.setdefault((section, name), {})[backend] = ns

    name_w = max(36, *(len(n) for _, n in order)) if order else 36
    col_w = 11
    print()
    print("=" * (name_w + 4 + col_w * len(BACKENDS) + 14))
    head = " " * (name_w + 2) + "".join(f"{b:>{col_w}}" for b in BACKENDS)
    head += f"{'jit/ffi':>{col_w}}{'jit/gi':>{col_w + 2}}"
    print(head)
    print("-" * len(head))
    last_section = None
    for section, name in order:
        if section != last_section:
            print(f"--- {section}" if section else "")
            last_section = section
        cells = by_key.get((section, name), {})
        row = f"  {name:<{name_w}}"
        for b in BACKENDS:
            ns = cells.get(b)
            row += f"{(f'{ns:.1f} ns' if ns is not None else '—'):>{col_w}}"
        jit, ffi, gi = cells.get("jit"), cells.get("ffi"), cells.get("gi")
        row += f"{(f'{ffi / jit:.2f}x' if jit and ffi else '—'):>{col_w}}"
        row += f"{(f'{gi / jit:.2f}x' if jit and gi else '—'):>{col_w + 2}}"
        print(row)


# If no --backend was passed, drive one subprocess per backend and
# collate the results into a single comparison table.
if not any(
    a == "--gi" or a == "--backend" or a.startswith("--backend=") for a in sys.argv[1:]
):
    per: dict[str, list[tuple[str, str, float | None]]] = {}
    for b in BACKENDS:
        ok, rows = _run_one(b)
        per[b] = rows
        # Echo each subprocess's raw output for debugging visibility.
        cmd = [
            sys.executable,
            str(_HERE / "examples/draw-bench/microbench.py"),
            f"--backend={b}",
        ]
        # We already ran it captured; just summarize per-backend status.
        sys.stdout.write(f"[{b}] {'ok' if ok else 'failed'} — {len(rows)} rows\n")
    _collate_and_print(per)
    sys.exit(0)

GoiBench, _BACKEND = setup_backend()


def _section(title: str) -> None:
    print(f"--- {title}")


def main() -> None:
    header("microbench", _BACKEND)

    # -- free functions --------------------------------------------------
    _section("free functions")
    nv = GoiBench.noop_void
    bench("noop_void   (0 args, void)", lambda: nv())
    ni = GoiBench.noop_int
    bench("noop_int    (0 args, int)", lambda: ni())
    f1 = GoiBench.in_1_int
    bench("in_1_int    (1 arg)", lambda: f1(42))
    f2 = GoiBench.in_2_int
    bench("in_2_int    (2 args)", lambda: f2(1, 2))
    f3 = GoiBench.in_3_int
    bench("in_3_int    (3 args)", lambda: f3(1, 2, 3))
    f4 = GoiBench.in_4_int
    bench("in_4_int    (4 args)", lambda: f4(1, 2, 3, 4))
    f5 = GoiBench.in_5_int
    bench("in_5_int    (5 args)", lambda: f5(1, 2, 3, 4, 5))
    f6 = GoiBench.in_6_int
    bench("in_6_int    (6 args)", lambda: f6(1, 2, 3, 4, 5, 6))
    fm = GoiBench.in_5_mixed
    bench("in_5_mixed  (i32,i64,f64,i32,u32)", lambda: fm(1, 2, 3.0, 4, 5))

    # -- direct C->Python callback loops --------------------------------
    if hasattr(GoiBench, "callback_no_args_loop"):
        _section("direct callbacks (C loop)")
        inner = 10_000
        outer = 1_000
        cb0 = GoiBench.callback_no_args_loop
        cbi = GoiBench.callback_int_loop
        cbo = GoiBench.callback_out_int_loop
        cbm = GoiBench.callback_mixed_loop
        cbu = GoiBench.callback_user_data_loop
        bench_inner("callback no args", lambda: cb0(lambda: None, inner), outer, inner)
        bench_inner(
            "callback int -> int", lambda: cbi(lambda _v: 1, inner), outer, inner
        )
        bench_inner(
            "callback int -> out int", lambda: cbo(lambda _v: 1, inner), outer, inner
        )
        bench_inner(
            "callback mixed -> int",
            lambda: cbm(lambda _a, _b, _c, _flag, _text: 1, inner),
            outer,
            inner,
        )
        bench_inner(
            "callback user-data",
            lambda: cbu(lambda _v, data: data, 1, inner),
            outer,
            inner,
        )

    if not hasattr(GoiBench, "Object"):
        print()
        print("  SKIP rest: GoiBench.Object not present — rebuild the bench typelib")
        return

    # -- GObject methods (mirror the drawing-app trace) ------------------
    _section("methods on GObject (bound)")
    obj = GoiBench.Object.new()
    other = GoiBench.Object.new()

    set_flag = obj.set_flag
    set_label = obj.set_label
    get_label = obj.get_label
    get_index = obj.get_index
    lookup = obj.lookup
    nth = obj.nth
    index_of = obj.index_of

    bench("set_flag(self, bool)", lambda: set_flag(True))
    bench("set_label(self, str)", lambda: set_label("hi"))
    bench("set_label(self, None)", lambda: set_label(None))
    bench("get_label(self) → str", lambda: get_label())
    bench("get_index(self) → int", lambda: get_index())
    bench("lookup(self, str) → GO", lambda: lookup("undo"))
    bench("nth(self, int) → GO", lambda: nth(0))
    bench("index_of(self, GO)→int", lambda: index_of(other))

    # Compare bound vs attribute-each-call — real apps usually do the
    # latter (`win.lookup_action(...)` resolves the descriptor each time).
    _section("methods on GObject (attr-each-call)")
    bench("set_flag attr-each", lambda: obj.set_flag(True))
    bench("lookup attr-each", lambda: obj.lookup("undo"))

    # -- property dispatch ----------------------------------------------
    _section("GObject property dispatch")
    get_prop = obj.get_property
    set_prop = obj.set_property
    bench("get_property('value')", lambda: get_prop("value"))
    bench("set_property('value', 42)", lambda: set_prop("value", 42))

    _section("Python-defined GObject.Property")
    if _BACKEND == "gi":
        from gi.repository import Gio, GObject
    else:
        from goi.repository import Gio, GObject

    class BenchProp(GObject.Object):
        __gtype_name__ = f"GoiBenchProp_{_BACKEND}"
        value = GObject.Property(type=int, default=0)

    prop_obj = BenchProp()

    def set_value() -> None:
        prop_obj.value = 42

    bench("plain attr get", lambda: prop_obj.value)
    bench("plain attr set", set_value)
    bench("props.value get", lambda: prop_obj.props.value)
    bench("get_property('value') py", lambda: prop_obj.get_property("value"))
    bench("set_property('value', 42)", lambda: prop_obj.set_property("value", 42))

    _section("Gio.ListModel row property fetch")
    row_gtype = getattr(BenchProp, "__goi_gtype__", getattr(BenchProp, "__gtype__"))
    store = Gio.ListStore.new(item_type=row_gtype)
    store.append(prop_obj)
    row = store.get_item(0)
    bench("get_item(0)", lambda: store.get_item(0))
    bench("cached row attr get", lambda: row.value)
    bench("get_item(0).value", lambda: store.get_item(0).value)
    bench("get_item(0).props.value", lambda: store.get_item(0).props.value)
    bench("get_item(0).get_property", lambda: store.get_item(0).get_property("value"))

    # -- signal emit (closure) ------------------------------------------
    _section("signal emit (GClosure)")
    obj.connect("tick", lambda _o: None)
    bench("emit tick (Python listener)", obj.tick, n=1_000_000)

    bare = GoiBench.Object.new()
    bench("emit tick (no listener)", bare.tick, n=1_000_000)


if __name__ == "__main__":
    main()
