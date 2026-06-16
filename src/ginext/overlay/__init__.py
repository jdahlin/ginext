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

"""Overlay system: namespace-scoped declarative customization.

Overlay modules in ``ginext/_overlays/<Ns>.py`` register adjustments
via a registrar exposed as ``<Namespace>.overlay`` during
``_load_namespace``; the registrar is removed once the overlay module
finishes importing.

Function overlays are decorators on the registrar; non-function
overlays (aliases, constants, bases, lifecycle hooks) are imperative
calls. Bodies that need to invoke the typelib's original use
``ginext.private.invoke``.
"""

from __future__ import annotations

from .bootstrap import load_overlay_module_for
from .callbacks import adapt_callback, callback_arg_types_for, callback_types
from .install import (
    async_result_names_for,
    class_bases_overlay_for,
    class_method_overlays_for,
    deprecations_proxy_for,
    hidden_attribute_names_for,
    is_attribute_hidden,
    is_class_method_hidden,
    install_class_overlay,
    install_module_overlay,
    keyword_only_after_for,
    method_arg_defaults_for,
    module_overlay_for,
    module_overlay_names,
    run_first_access,
)
from .registrar import OverlayRegistrar
from .types import (
    AliasOverlay,
    BodyOverlay,
    ClassBasesOverlay,
    ConstantOverlay,
    FirstAccessHook,
    LifecycleConfig,
)

__all__ = [
    "AliasOverlay",
    "BodyOverlay",
    "ClassBasesOverlay",
    "ConstantOverlay",
    "FirstAccessHook",
    "LifecycleConfig",
    "OverlayRegistrar",
    "adapt_callback",
    "callback_arg_types_for",
    "callback_types",
    "class_bases_overlay_for",
    "async_result_names_for",
    "class_method_overlays_for",
    "deprecations_proxy_for",
    "hidden_attribute_names_for",
    "is_attribute_hidden",
    "is_class_method_hidden",
    "install_class_overlay",
    "install_module_overlay",
    "keyword_only_after_for",
    "load_overlay_module_for",
    "method_arg_defaults_for",
    "module_overlay_for",
    "module_overlay_names",
    "run_first_access",
]
