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

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

type CallbackArgType = type | str
type CallbackArgTypes = dict[str, tuple[CallbackArgType, ...]]


@dataclass(frozen=True)
class BodyOverlay:
    name: str
    body: Callable[..., Any]
    as_classmethod: bool = False
    as_staticmethod: bool = False
    as_descriptor: bool = False
    inject_fn: bool = False
    callback_arg_types: CallbackArgTypes = field(default_factory=dict)


@dataclass(frozen=True)
class AliasOverlay:
    name: str
    target_path: str


@dataclass(frozen=True)
class ConstantOverlay:
    name: str
    value: object


@dataclass(frozen=True)
class DeprecatedOverlay:
    name: str
    value: object
    replacement: str


@dataclass(frozen=True)
class ClassBasesOverlay:
    qname: str
    bases: tuple[type | str, ...]


@dataclass(frozen=True)
class ConstructorOverlay:
    # pygobject-compat-style constructor: installs __new__ (and an optional
    # __init__) eagerly at class-build time. `new` is called as new(cls, ...);
    # while it runs the overlay module's namespace global (named `ns`) is bound
    # to the per-profile namespace of `cls`, so nested constructor calls resolve
    # to the right profile (e.g. compat vs native).
    ns: str
    class_name: str
    new: Callable[..., Any]
    init: Callable[..., Any] | None = None


@dataclass
class FirstAccessHook:
    callback: Callable[[], Any]
    env_gate: str | None = None
    on_error: Literal["raise", "warn"] = "raise"


@dataclass
class LifecycleConfig:
    first_access: list[FirstAccessHook] = field(default_factory=list)
    first_access_ran: bool = False
    first_access_running: bool = False


type ModuleEntry = BodyOverlay | AliasOverlay | ConstantOverlay | DeprecatedOverlay
