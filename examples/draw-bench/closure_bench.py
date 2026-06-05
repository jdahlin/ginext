"""
closure_bench - focused C-to-Python closure invocation benchmark.

Unlike microbench.py's signal section, these rows call Python callbacks
directly from tight C loops in GoiBench. That keeps Python->C invoke and
GObject signal emission out of the denominator, so ffi/jit closure backend
work can be compared against the path it actually changes.
"""

from __future__ import annotations

from _bench_common import setup_backend, header, bench_inner


GoiBench, _BACKEND = setup_backend()


def _section(title: str) -> None:
    print(f"--- {title}")


def main() -> None:
    header("closure_bench", _BACKEND)

    if not hasattr(GoiBench, "callback_no_args_loop"):
        print("  SKIP: rebuild the GoiBench typelib for direct callback loops")
        return

    inner = 10_000
    outer = 1_000

    _section("direct callbacks (C loop)")
    cb0 = GoiBench.callback_no_args_loop
    cbi = GoiBench.callback_int_loop
    cbo = GoiBench.callback_out_int_loop
    cbm = GoiBench.callback_mixed_loop
    cbu = GoiBench.callback_user_data_loop

    bench_inner("callback no args", lambda: cb0(lambda: None, inner), outer, inner)
    bench_inner("callback int -> int", lambda: cbi(lambda _v: 1, inner), outer, inner)
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
        "callback user-data", lambda: cbu(lambda _v, data: data, 1, inner), outer, inner
    )


if __name__ == "__main__":
    main()
