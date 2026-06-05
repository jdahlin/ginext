#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GJS_BIN="${GJS:-gjs}"

if ! command -v "$GJS_BIN" >/dev/null 2>&1; then
    echo "error: system gjs not found; set GJS=/path/to/gjs or install gjs" >&2
    exit 127
fi

if [[ -n "${GOI_BENCH_BUILDDIR:-}" ]]; then
    BENCH_DIR="$GOI_BENCH_BUILDDIR"
else
    BENCH_DIR="$(
        find "$ROOT/build" -path '*/packages/typelib/GoiBench-1.0.typelib' -printf '%T@ %h\n' 2>/dev/null \
            | sort -nr \
            | awk 'NR == 1 {print $2}'
    )"
fi

if [[ -z "${BENCH_DIR:-}" || ! -f "$BENCH_DIR/GoiBench-1.0.typelib" ]]; then
    echo "error: GoiBench-1.0.typelib not found; run 'make build' first or set GOI_BENCH_BUILDDIR" >&2
    exit 1
fi

if [[ ! -f "$BENCH_DIR/libgoibench.so" ]]; then
    echo "error: libgoibench.so not found next to $BENCH_DIR/GoiBench-1.0.typelib" >&2
    exit 1
fi

export GI_TYPELIB_PATH="$BENCH_DIR${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
export LD_LIBRARY_PATH="$BENCH_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export GOI_BENCH_GJS_VERSION="$("$GJS_BIN" --version 2>/dev/null || printf 'gjs')"

exec "$GJS_BIN" "$ROOT/examples/draw-bench/gjs_microbench.js" "$@"
