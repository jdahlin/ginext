# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

from collections.abc import Callable, Sequence

from .. import private


def _parse_signal(gtype: int, detailed_signal: str) -> tuple[int, int]:
    parsed = private.invoke(
        "GObject", "signal_parse_name", detailed_signal, gtype, True
    )
    ok, signal_id, detail = parsed
    if not ok:
        raise ValueError(f"no such signal: {detailed_signal}")
    return int(signal_id), int(detail)


def add_emission_hook(
    gtype: int, detailed_signal: str, callback: Callable[[object], object]
) -> int:
    signal_id, detail = _parse_signal(gtype, detailed_signal)

    def hook(*args: object) -> object:
        param_values = args[-1] if args else ()
        if not isinstance(param_values, Sequence):
            param_values = ()
        instance = param_values[0] if param_values else None
        return callback(instance)

    return int(
        private.invoke(
            "GObject", "signal_add_emission_hook", signal_id, detail, hook
        )
    )


def remove_emission_hook(gtype: int, detailed_signal: str, hook_id: int) -> None:
    signal_id, _detail = _parse_signal(gtype, detailed_signal)
    private.invoke("GObject", "signal_remove_emission_hook", signal_id, hook_id)
