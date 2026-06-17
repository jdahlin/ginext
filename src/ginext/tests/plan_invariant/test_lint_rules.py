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

"""Invariant tests: lint rules that must stay enabled in pyproject.toml.

DO NOT modify this file to make tests pass — fix the lint configuration instead.
These tests exist because automated agents have repeatedly disabled or weakened
rules (getattr with constant strings, unparenthesized multi-exception except)
that enforce important code-quality constraints.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

_PYPROJECT = Path(__file__).parents[4] / "pyproject.toml"
_PRE_COMMIT = Path(__file__).parents[4] / ".pre-commit-config.yaml"


@pytest.fixture(scope="module")
def ruff_config() -> dict:  # type: ignore[type-arg]
    data = tomllib.loads(_PYPROJECT.read_text())
    return data["tool"]["ruff"]["lint"]  # type: ignore[return-value]


@pytest.fixture(scope="module")
def pre_commit_hooks() -> list[dict]:  # type: ignore[type-arg]
    import yaml  # type: ignore[import-untyped]

    data = yaml.safe_load(_PRE_COMMIT.read_text())
    return [hook for repo in data["repos"] for hook in repo["hooks"]]


# ── ruff rules that must stay in extend-select ────────────────────────────────

REQUIRED_RUFF_RULES = [
    ("B009", "getattr with constant string — use direct attribute access"),
    ("B010", "setattr with constant string — use direct attribute access"),
    ("S110", "try-except-pass — use contextlib.suppress instead"),
    ("RUF012", "mutable class-level default without ClassVar"),
]


@pytest.mark.parametrize(
    "rule,reason", REQUIRED_RUFF_RULES, ids=[r for r, _ in REQUIRED_RUFF_RULES]
)
def test_ruff_rule_is_selected(rule: str, reason: str, ruff_config: dict) -> None:  # type: ignore[type-arg]
    selected = ruff_config.get("extend-select", [])
    # A rule is covered if it or its prefix category is selected
    covered = any(
        rule == entry or (len(entry) < len(rule) and rule.startswith(entry))
        for entry in selected
    )
    assert covered, (
        f"ruff rule {rule!r} ({reason}) must be in [tool.ruff.lint] extend-select. "
        f"Do not remove it — fix the violation instead."
    )


FORBIDDEN_RUFF_IGNORES = [
    ("B009", "getattr with constant string must not be silenced globally"),
    ("B010", "setattr with constant string must not be silenced globally"),
    ("S110", "try-except-pass must not be silenced globally"),
]


@pytest.mark.parametrize(
    "rule,reason", FORBIDDEN_RUFF_IGNORES, ids=[r for r, _ in FORBIDDEN_RUFF_IGNORES]
)
def test_ruff_rule_not_globally_ignored(
    rule: str, reason: str, ruff_config: dict
) -> None:  # type: ignore[type-arg]
    ignored = ruff_config.get("ignore", [])
    assert rule not in ignored, (
        f"ruff rule {rule!r} must not appear in [tool.ruff.lint] ignore. "
        f"Reason: {reason}."
    )


# ── pre-commit hooks that must stay present ───────────────────────────────────

REQUIRED_HOOKS = [
    ("no-literal-getattr", "blocks getattr(obj, 'constant') at commit time"),
    ("no-unparenthesized-except", "blocks except X, Y: (must be except (X, Y):)"),
    (
        "no-wide-except",
        "blocks except clauses with 4+ types — split or use a named tuple",
    ),
]


@pytest.mark.parametrize(
    "hook_id,reason", REQUIRED_HOOKS, ids=[h for h, _ in REQUIRED_HOOKS]
)
def test_pre_commit_hook_present(
    hook_id: str,
    reason: str,
    pre_commit_hooks: list[dict],  # type: ignore[type-arg]
) -> None:
    ids = [h["id"] for h in pre_commit_hooks]
    assert hook_id in ids, (
        f"pre-commit hook {hook_id!r} is missing from .pre-commit-config.yaml. "
        f"Reason: {reason}. Do not remove it."
    )
