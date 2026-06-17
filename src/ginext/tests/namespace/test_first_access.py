# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, see <http://www.gnu.org/licenses/>.

"""Port of goi/tests/test_namespace_first_access.py."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from collections.abc import Generator

import pytest

from ginext.namespace import Namespace
from ginext.overlay import state
from ginext.overlay.types import FirstAccessHook, LifecycleConfig


@contextlib.contextmanager
def _temporary_lifecycle(ns_name: str, cfg: LifecycleConfig) -> Generator[None]:
    sentinel = object()
    previous = state.lifecycle.get(ns_name, sentinel)
    state.lifecycle[ns_name] = cfg
    try:
        yield
    finally:
        if previous is sentinel:
            state.lifecycle.pop(ns_name, None)
        else:
            state.lifecycle[ns_name] = cast("LifecycleConfig", previous)


def _fresh_namespace(name: str = "GLib", version: str = "2.0") -> Namespace:
    return Namespace(name, version)


def _make_ns_with_call(
    *, env_gate: str | None = None, on_error: Literal["raise", "warn"] = "raise"
) -> tuple[LifecycleConfig, Namespace, list[str]]:
    calls: list[str] = []
    cfg = LifecycleConfig(
        first_access=[
            FirstAccessHook(
                callback=lambda: calls.append("fired"),
                env_gate=env_gate,
                on_error=on_error,
            )
        ]
    )
    return cfg, _fresh_namespace(), calls


def test_class_lookup_fires_call_on_first_access() -> None:
    cfg, ns, calls = _make_ns_with_call()

    with _temporary_lifecycle("GLib", cfg):
        _ = ns.MainLoop

    assert calls == ["fired"]
    assert cfg.first_access_ran is True


def test_function_lookup_fires_call_on_first_access() -> None:
    cfg, ns, calls = _make_ns_with_call()

    with _temporary_lifecycle("GLib", cfg):
        _ = ns.get_user_name

    assert calls == ["fired"]
    assert cfg.first_access_ran is True


def test_does_not_refire_on_subsequent_accesses() -> None:
    cfg, ns, calls = _make_ns_with_call()

    with _temporary_lifecycle("GLib", cfg):
        _ = ns.MainLoop
        _ = ns.get_user_name
        _ = ns.Variant
        _ = ns.Bytes

    assert calls == ["fired"]


def test_dunder_lookup_does_not_fire() -> None:
    cfg, ns, calls = _make_ns_with_call()

    with _temporary_lifecycle("GLib", cfg), pytest.raises(AttributeError):
        _ = ns.__nope_definitely_missing__

    assert calls == []
    assert cfg.first_access_ran is False


def test_env_gate_skips_the_call_but_consumes_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_FIRST_ACCESS_TEST_SKIP", "0")
    cfg, ns, calls = _make_ns_with_call(env_gate="GINEXT_FIRST_ACCESS_TEST_SKIP")

    with _temporary_lifecycle("GLib", cfg):
        _ = ns.MainLoop

    assert calls == []
    assert cfg.first_access_ran is True


def test_env_gate_default_runs_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GINEXT_FIRST_ACCESS_TEST_SKIP", raising=False)
    cfg, ns, calls = _make_ns_with_call(env_gate="GINEXT_FIRST_ACCESS_TEST_SKIP")

    with _temporary_lifecycle("GLib", cfg):
        _ = ns.MainLoop

    assert calls == ["fired"]


def test_warn_on_error_does_not_propagate(capsys: pytest.CaptureFixture[str]) -> None:
    def boom() -> None:
        raise RuntimeError("simulated first-access failure")

    cfg = LifecycleConfig(
        first_access=[FirstAccessHook(callback=boom, on_error="warn")]
    )
    ns = _fresh_namespace()

    with _temporary_lifecycle("GLib", cfg):
        _ = ns.MainLoop

    captured = capsys.readouterr()
    assert "GLib.boom" in captured.err
    assert "simulated first-access failure" in captured.err


def test_raise_on_error_propagates() -> None:
    def boom() -> None:
        raise RuntimeError("hard failure")

    cfg = LifecycleConfig(
        first_access=[FirstAccessHook(callback=boom, on_error="raise")]
    )
    ns = _fresh_namespace()

    with (
        _temporary_lifecycle("GLib", cfg),
        pytest.raises(RuntimeError, match="hard failure"),
    ):
        _ = ns.MainLoop


def test_multiple_calls_run_in_declared_order() -> None:
    log: list[str] = []
    cfg = LifecycleConfig(
        first_access=[
            FirstAccessHook(callback=lambda: log.append("first")),
            FirstAccessHook(callback=lambda: log.append("second")),
            FirstAccessHook(callback=lambda: log.append("third")),
        ]
    )
    ns = _fresh_namespace()

    with _temporary_lifecycle("GLib", cfg):
        _ = ns.MainLoop

    assert log == ["first", "second", "third"]
