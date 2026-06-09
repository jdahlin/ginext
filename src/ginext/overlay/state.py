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

from __future__ import annotations

from .types import (
    BodyOverlay,
    ClassBasesOverlay,
    ConstructorOverlay,
    DeprecatedOverlay,
    LifecycleConfig,
    ModuleEntry,
)


module_overlays: dict[tuple[str, str], ModuleEntry] = {}
# Per-namespace mutable deprecated-entry registry.  Keyed by (ns, name).
# Separate from module_overlays so __delattr__ can remove entries at runtime
# and _deprecations proxy can expose a mutable view to pygobject-compat code.
deprecated_entries: dict[tuple[str, str], DeprecatedOverlay] = {}
hidden_attribute_names: dict[str, set[str]] = {}
class_method_overlays: dict[tuple[str, str], dict[str, BodyOverlay]] = {}
class_bases_overlays: dict[tuple[str, str], ClassBasesOverlay] = {}
# (namespace, class) -> pygobject-compat constructor overlay (__new__/__init__).
constructor_overlays: dict[tuple[str, str], ConstructorOverlay] = {}
# (namespace, class) -> {method_name: {param_name: default_value}}
method_arg_defaults: dict[tuple[str, str], dict[str, dict[str, object]]] = {}
# (namespace, owner) -> {method_name: cutoff}.  `owner` is the class name, or
# "" for module-level functions. Visible arguments at index >= cutoff become
# keyword-only: they may only be passed by name, never positionally.
keyword_only_args: dict[tuple[str, str], dict[str, int]] = {}
# (namespace, class, async_method) -> OUT-param names for the finish result,
# wrapped into a ginext.aio.NamedReturn so awaited callers can read OUT values
# by name (e.g. `result.out_fd_list`).
async_result_names: dict[tuple[str, str, str], tuple[str, ...]] = {}
lifecycle: dict[str, LifecycleConfig] = {}


def lifecycle_for(ns: str) -> LifecycleConfig:
    cfg = lifecycle.get(ns)
    if cfg is None:
        cfg = LifecycleConfig()
        lifecycle[ns] = cfg
    return cfg


def reset_first_access() -> None:
    """Clear the first-access "ran" flags so the hooks re-evaluate on the next
    namespace access.

    Used by ``ginext.defaults.reset_caches()`` for test isolation: that pops the
    namespace modules so they rebuild, but the overlay lifecycle lives here and
    survives. Without this, a prior access that *skipped* a gated hook (e.g.
    GTK auto-init with ``GINEXT_GTK_AUTO_INIT=0``) still marks first-access done,
    so a later test never runs the hook — leaving GTK uninitialized, which on
    Windows crashes the next widget construction in gtk_css_static_style.
    The registered hooks are kept; only the run/running flags reset.
    """
    for cfg in lifecycle.values():
        cfg.first_access_ran = False
        cfg.first_access_running = False
