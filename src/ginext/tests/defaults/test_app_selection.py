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

"""App-distribution selection drives which gidefaults.py is loaded.

Order:
1. GINEXT_APP=name selects explicitly.
2. Else infer from __main__.__spec__.name -> packages_distributions().
3. If inference is ambiguous, raise (unsuffixed import needs override).
"""

from __future__ import annotations

import pytest


def test_explicit_app_env_uses_named_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GINEXT_APP", "nonexistent-app")

    import ginext

    # An explicit, missing app produces a clear error, not a silent
    # fallback to highest-installed.
    with pytest.raises((LookupError, RuntimeError, ImportError)):
        ginext.defaults.load_app_defaults()


def test_no_app_env_no_inferable_main_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pytest's __main__ does not map to a dist with gidefaults.py.
    The loader should return None (not raise)."""
    monkeypatch.delenv("GINEXT_APP", raising=False)

    import ginext

    result = ginext.defaults.load_app_defaults()
    assert result is None or result == {}


def test_ambiguous_inference_raises_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the top-level package maps to multiple distributions, an
    unsuffixed import cannot pick a default. The loader must raise."""
    import ginext

    # Simulate ambiguity via the documented test hook.
    monkeypatch.setattr(
        ginext.defaults,
        "_packages_distributions_for_test",
        lambda: {"ambiguouspkg": ["distA", "distB"]},
    )
    monkeypatch.setattr(
        ginext.defaults,
        "_main_package_for_test",
        lambda: "ambiguouspkg",
    )

    with pytest.raises((RuntimeError, LookupError)) as excinfo:
        ginext.defaults.load_app_defaults()

    # Error message should name the candidate distributions.
    assert "distA" in str(excinfo.value) or "distB" in str(excinfo.value)


def test_explicit_app_resolves_ambiguity(monkeypatch: pytest.MonkeyPatch) -> None:
    """If inference is ambiguous, GINEXT_APP should resolve it."""
    monkeypatch.setenv("GINEXT_APP", "distA")
    import ginext

    monkeypatch.setattr(
        ginext.defaults,
        "_packages_distributions_for_test",
        lambda: {"ambiguouspkg": ["distA", "distB"]},
    )

    # Should not raise an ambiguity error (may still raise LookupError
    # because distA doesn't actually exist on disk).
    try:
        ginext.defaults.load_app_defaults()
    except (LookupError, ImportError):
        pass
    except RuntimeError as exc:
        assert "ambig" not in str(exc).lower()


def test_app_defaults_cached_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated loads memoize the result without re-walking distribution
    metadata on every call."""
    import ginext

    calls = 0

    def fake_uncached() -> dict[str, str]:
        nonlocal calls
        calls += 1
        return {"Gtk": "4.0"}

    monkeypatch.setattr(
        ginext.defaults, "_load_app_defaults_uncached_for_test", fake_uncached
    )
    # Start cold for the current app key so the first load runs the uncached path.
    monkeypatch.setattr(ginext.defaults, "_project_defaults_cache", None)

    a = ginext.defaults.load_app_defaults()
    b = ginext.defaults.load_app_defaults()
    assert a == b == {"Gtk": "4.0"}
    assert calls == 1  # memoized: the uncached path ran exactly once
