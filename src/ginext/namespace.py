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

import keyword
import threading
import types
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .overlay.registrar import OverlayRegistrar

from . import abi, private
from .classbuild import ClassBuilder
from .enum import EnumBuilder
from .method import FunctionBuilder
from .overlay import (
    hidden_attribute_names_for,
    is_attribute_hidden,
    install_module_overlay,
    module_overlay_for,
    module_overlay_names,
    deprecations_proxy_for,
    run_first_access,
    state as _overlay_state,
)
from .overlay.types import DeprecatedOverlay
from .record import RecordBuilder


class Namespace:
    if TYPE_CHECKING:
        overlay: OverlayRegistrar  # set only during overlay module loading

    def __init__(
        self, name: str, version: str | None, *, profile: abi.ABIProfile = abi.NATIVE
    ):
        self._name = name
        self._version = private.require_namespace(name, version)
        self._profile = profile
        self._version_tuple = tuple(int(c) for c in self._version.split("."))
        self._member_lock = threading.RLock()
        self.context = abi.NamespaceContext(self._name, self._version, self._profile)
        self.gimeta = types.SimpleNamespace(
            name=self._name,
            version=self._version,
            profile=self._profile,
        )
        self._class_builder = ClassBuilder(self.context)
        self._record_builder = RecordBuilder(self.context)
        self._enum_builder = EnumBuilder(self.context)
        self._function_builder = FunctionBuilder(self.context)

    @property
    def __name__(self) -> str:
        return self._name

    @property
    def __version__(self) -> tuple[int, ...]:
        return self._version_tuple

    def __repr__(self) -> str:
        return f"<{self._profile.module_name(self.__name__)} {self._version}>"

    def __dir__(self) -> list[str]:
        namespace_name = self.__name__
        names = set(private.namespace_dir(namespace_name, self._version))
        names.update(vars(self))
        names.update(module_overlay_names(namespace_name))
        if namespace_name == "GObject":
            names.add("Signal")
        names.difference_update(hidden_attribute_names_for(namespace_name))
        return sorted(names)

    def __getattr__(self, name: str) -> Any:
        with self._member_lock:
            cached = vars(self).get(name)
            if cached is not None:
                return cached

            # Dunders skipped — Python probes __wrapped__ etc. and shouldn't
            # trigger first-access side effects (e.g. a namespace init hook).
            if not name.startswith("_"):
                run_first_access(self._name)

            if name == "_deprecations":
                return deprecations_proxy_for(self._name)

            if self._name == "GObject" and name == "Signal":
                from .signal.descriptor import SignalDescriptor

                setattr(self, name, SignalDescriptor)
                return SignalDescriptor

            entry = module_overlay_for(self.__name__, name)
            if entry is not None:
                value = install_module_overlay(self, name, entry)
                # Deprecated overlays must NOT be cached: every access must
                # go through __getattr__ so the warning fires each time.
                if not isinstance(entry, DeprecatedOverlay):
                    setattr(self, name, value)
                return value

            lookup_name = (
                name[:-1]
                if name.endswith("_") and keyword.iskeyword(name[:-1])
                else name
            )
            kind, info = private.namespace_find(
                self.__name__, self._version, lookup_name
            )
            if is_attribute_hidden(self.__name__, lookup_name):
                raise AttributeError(name)

            # Deferred: ginext.GIRepository is a lazily-resolved GI namespace that
            # isn't importable while ginext/__init__.py is still importing this
            # module (bootstrap cycle). By first attribute access it is loaded.
            from ginext.GIRepository import (
                EnumInfo,
                FlagsInfo,
                ConstantInfo,
                ObjectInfo,
                InterfaceInfo,
                StructInfo,
                UnionInfo,
                FunctionInfo,
            )

            match info:
                case ConstantInfo(value=value):
                    pass
                # FlagsInfo must precede EnumInfo: it is a subclass of EnumInfo
                case FlagsInfo():
                    value = self._enum_builder.build_flags(name, info)
                case EnumInfo():
                    value = self._enum_builder.build_enum(name, info)
                case FunctionInfo():
                    value = self._function_builder.build_function(info)
                case InterfaceInfo():
                    value = self._class_builder.build_object_or_interface(info)
                case ObjectInfo():
                    value = self._class_builder.build_object_or_interface(info)
                case StructInfo():
                    value = self._record_builder.build_record(info)
                case UnionInfo():
                    value = self._record_builder.build_record(info)
                case _:
                    raise AttributeError(
                        f"{self._name}.{name}: GI member kind {kind!r} is not supported"
                    )
            setattr(self, name, value)
            return value

    def cached_member(self, name: str) -> type | None:
        """Return the built class cached under ``name``, or None.

        The namespace ``__dict__`` is the by-name build cache. A class is
        registered here (see :meth:`cache_member`) before its overlays run, so
        a lookup that re-enters during the build — e.g. an overlay that
        references the class still being built — resolves via ordinary
        attribute access instead of triggering another build.
        """
        cached = vars(self).get(name)
        return cached if isinstance(cached, type) else None

    def cache_member(self, name: str, cls: type) -> None:
        """Register a freshly built class as ``name`` so ``__getattr__``
        short-circuits on later access, and so a re-entrant lookup during the
        same build resolves to it instead of recursing into another build."""
        setattr(self, name, cls)

    def __delattr__(self, name: str) -> None:
        # Remove from instance __dict__ (may raise AttributeError if not there)
        try:
            super().__delattr__(name)
        except AttributeError:
            pass
        # Also remove from the deprecated-entries registry so hasattr() returns
        # False after deletion (mirrors pygobject's Namespace.__delattr__).
        _overlay_state.deprecated_entries.pop((self._name, name), None)
        _overlay_state.module_overlays.pop((self._name, name), None)
