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

# Ratchet: residual explicit Any not yet removed (adopting --disallow-any-explicit
# incrementally). Remove this line once the file is Any-clean.
# mypy: disable-error-code="explicit-any"

"""Tests for the ``overlay.keyword_only(...)`` declaration: it shapes both the
introspected signature (tail params become KEYWORD_ONLY) and the call itself
(passing those params positionally raises TypeError)."""

from __future__ import annotations

from typing import Any, cast

import inspect

import pytest

from ginext.overlay import state


class _FakeNamespace:
    """Minimal stand-in: the registrar only reads ``__name__`` for keyword_only."""

    __name__ = "GLib"
    _version = "2.0"


@pytest.fixture
def kw_only_state() -> Any:
    """Isolate ``state.keyword_only_args`` and drop callables rebuilt with an
    overlay so later tests see the un-overlaid form again."""
    saved = {k: dict(v) for k, v in state.keyword_only_args.items()}
    rebuilt: list[tuple[object, str]] = []
    yield rebuilt
    state.keyword_only_args.clear()
    state.keyword_only_args.update(saved)
    for owner, name in rebuilt:
        try:
            delattr(owner, name)
        except AttributeError:
            pass


def _force_fresh(owner: object, name: str, rebuilt: list[tuple[object, str]]) -> None:
    """Drop any cached build of ``owner.name`` so the next access rebuilds it
    against the seeded overlay state, and schedule a post-test reset."""
    try:
        delattr(owner, name)
    except AttributeError:
        pass
    rebuilt.append((owner, name))


# ── registrar / accessor ────────────────────────────────────────────────


def test_registrar_records_method_and_function_cutoffs(kw_only_state: Any) -> None:
    from ginext.overlay import keyword_only_after_for
    from ginext.overlay.registrar import OverlayRegistrar

    registrar = OverlayRegistrar(cast("Any", _FakeNamespace()))
    registrar.keyword_only("KeyFile", "set_string", after=1)
    registrar.keyword_only("spawn_async", after=2)

    assert keyword_only_after_for("GLib", "KeyFile", "set_string") == 1
    assert keyword_only_after_for("GLib", "", "spawn_async") == 2
    assert keyword_only_after_for("GLib", "KeyFile", "absent") is None


def test_registrar_rejects_negative_cutoff(kw_only_state: Any) -> None:
    from ginext.overlay.registrar import OverlayRegistrar

    with pytest.raises(ValueError, match="must be >= 0"):
        OverlayRegistrar(cast("Any", _FakeNamespace())).keyword_only(
            "spawn_async", after=-1
        )


# ── module-level function ───────────────────────────────────────────────


def test_module_function_signature_and_enforcement(kw_only_state: Any) -> None:
    from ginext import GLib

    state.keyword_only_args[("GLib", "")] = {"spawn_async": 1}
    _force_fresh(GLib, "spawn_async", kw_only_state)

    spawn_async = cast("Any", GLib.spawn_async)
    kinds = {p.name: p.kind for p in inspect.signature(spawn_async).parameters.values()}
    assert kinds["working_directory"] is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert kinds["argv"] is inspect.Parameter.KEYWORD_ONLY
    assert kinds["flags"] is inspect.Parameter.KEYWORD_ONLY

    with pytest.raises(TypeError, match="keyword-only"):
        spawn_async(".", ["/bin/true"])


# ── object-class method ─────────────────────────────────────────────────


def test_object_method_signature_and_enforcement(kw_only_state: Any) -> None:
    from ginext import Gio

    state.keyword_only_args[("Gio", "Subprocess")] = {"communicate_utf8": 1}
    _force_fresh(Gio.Subprocess, "communicate_utf8", kw_only_state)

    method = Gio.Subprocess.communicate_utf8
    params = list(inspect.signature(method).parameters.values())
    kinds = {p.name: p.kind for p in params}
    assert kinds["self"] is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert kinds["stdin_buf"] is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert kinds["cancellable"] is inspect.Parameter.KEYWORD_ONLY


def test_keyword_only_call_dispatches_into_c(kw_only_state: Any) -> None:
    """A successful by-keyword call still reaches the underlying C function."""
    from ginext import GLib

    state.keyword_only_args[("GLib", "KeyFile")] = {"set_string": 1}
    _force_fresh(GLib.KeyFile, "set_string", kw_only_state)

    key_file = GLib.KeyFile()
    key_file.set_string("group", key="name", string="value")
    assert key_file.get_string("group", "name") == "value"

    with pytest.raises(TypeError, match="keyword-only"):
        key_file.set_string("group", "name", "value")


def test_after_zero_makes_everything_keyword_only(kw_only_state: Any) -> None:
    from ginext import GLib

    state.keyword_only_args[("GLib", "")] = {"spawn_async": 0}
    _force_fresh(GLib, "spawn_async", kw_only_state)

    spawn_async = cast("Any", GLib.spawn_async)
    params = inspect.signature(spawn_async).parameters.values()
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params)
    with pytest.raises(TypeError, match="keyword-only"):
        spawn_async(".")
