#!/usr/bin/env bash
# Run mypy with a self-healing incremental cache.
#
# mypy 2.1.0 (our pinned version) can abort with "INTERNAL ERROR" when handed a
# stale or version-skewed incremental cache — e.g. a .mypy_cache restored from a
# different commit via CI's cache. That crash is what previously forced
# --no-incremental everywhere. This wrapper keeps the speed of an incremental
# cache but makes the cache a pure optimization: on an INTERNAL ERROR it drops
# the cache directory and retries once from a clean cache, so a poisoned cache
# can never turn into a red pipeline.
#
# Usage: ci/run-mypy.sh <cache-dir> <command...>
#   where <command...> is the full mypy invocation (e.g. `uv run mypy --strict
#   src/`). The wrapper appends `--cache-dir=<cache-dir>` to it.
set -uo pipefail

cache_dir=$1
shift
cmd=("$@")

log=$(mktemp)
trap 'rm -f "$log"' EXIT

run_with_cache() {
    "${cmd[@]}" --cache-dir="$cache_dir" 2>&1 | tee "$log"
    return ${PIPESTATUS[0]}
}

run_with_cache
status=$?

if [[ $status -ne 0 ]] && {
    grep -q "INTERNAL ERROR" "$log" ||
    grep -q 'Cannot find implementation or library stub for module named "ginext"' "$log"
}; then
    echo "ci/run-mypy.sh: mypy cache at ${cache_dir} looks stale — wiping and retrying once" >&2
    rm -rf -- "$cache_dir"
    run_with_cache
    status=$?
fi

exit "$status"
