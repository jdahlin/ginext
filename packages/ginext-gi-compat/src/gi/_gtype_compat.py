# Copyright 2026 Johan Dahlin
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

"""Monkey-patch GTypeMeta and GType with pygobject-compat additions.

This module is imported once at gi-compat load time (from _gi.py) and adds
the methods/properties that pygobject exposes on GType but that core ginext
does not provide:
  - GType.INVALID constant
  - GTypeMeta.pytype setter
  - GTypeMeta.is_instantiatable()
  - GTypeMeta.fundamental property
  - GTypeMeta.from_name() classmethod
  - GTypeMeta.parent property
"""

from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def _install() -> None:
    from ginext import abi, features
    from ginext.gobject.gtype import GType, GTypeMeta, compat_gtype_from_raw
    from ginext.gobject.resolve import classbuild_module, gobject_repo

    if getattr(GTypeMeta, "_gi_compat_installed", False):
        return

    # --- pytype setter ---
    _original_pytype_getter = GTypeMeta.__dict__["pytype"].fget

    def _pytype_setter(cls: Any, value: type | None) -> None:
        classbuild = classbuild_module()
        classes: dict[tuple[str, int], type] = classbuild._classes_by_gtype
        if features.is_enabled(features.PYGOBJECT_COMPAT):
            key = (abi.PYGOBJECT.name, int(cls))
        else:
            gimeta = vars(cls).get("gimeta")
            profile = gimeta.profile if gimeta is not None else abi.NATIVE
            key = (profile.name, int(cls))
        if value is None:
            classes.pop(key, None)
        else:
            classes[key] = value

    GTypeMeta.pytype = property(_original_pytype_getter, _pytype_setter)  # type: ignore[assignment]

    # --- is_instantiatable() ---
    def _is_instantiatable(cls: Any) -> bool:
        GObject = gobject_repo()
        return bool(
            GObject.type_test_flags(int(cls), GObject.TypeFundamentalFlags.INSTANTIATABLE)
        )

    GTypeMeta.is_instantiatable = _is_instantiatable  # type: ignore[attr-defined]

    # --- fundamental property ---
    def _fundamental_fget(cls: Any) -> "type[GType]":
        GObject = gobject_repo()
        raw = int(GObject.type_fundamental(int(cls)))
        return compat_gtype_from_raw(raw, GObject.type_name(raw))

    GTypeMeta.fundamental = property(_fundamental_fget)  # type: ignore[assignment]

    # --- from_name() classmethod ---
    def _from_name(cls: Any, name: str) -> "type[GType]":
        if not name:
            return GType.INVALID  # type: ignore[attr-defined]
        GObject = gobject_repo()
        raw = int(GObject.type_from_name(name))
        if raw == 0:
            return GType.INVALID  # type: ignore[attr-defined]
        return compat_gtype_from_raw(raw, name)

    GTypeMeta.from_name = classmethod(_from_name)  # type: ignore[attr-defined]

    # --- parent property ---
    def _parent_fget(cls: Any) -> "type[GType] | None":
        GObject = gobject_repo()
        raw = int(GObject.type_parent(int(cls)))
        if raw == 0:
            return None
        return compat_gtype_from_raw(raw, GObject.type_name(raw))

    GTypeMeta.parent = property(_parent_fget)  # type: ignore[assignment]

    # --- GType.INVALID constant ---
    _invalid_cls = type(
        "TYPE_INVALID",
        (GType,),
        {
            "__module__": "ginext.gobject.gtype",
            "gimeta": types.SimpleNamespace(gtype=0, profile=abi.NATIVE),
            "gtype_name": "",
        },
    )
    GType.INVALID = _invalid_cls  # type: ignore[attr-defined]

    GTypeMeta._gi_compat_installed = True  # type: ignore[attr-defined]



def _install_record_compat() -> None:
    """Add __info__ support to RecordMeta and RecordBase for pygobject compat."""
    from ginext import abi, private
    from ginext.record import RecordBuilder, RecordMeta, RecordBase

    if getattr(RecordMeta, "_gi_compat_installed", False):
        return

    _original_meta_getattr = RecordMeta.__getattr__

    def _meta_getattr(cls: Any, name: str) -> object:
        if name == "__info__":
            return getattr(cls.gimeta, "info", None)
        return _original_meta_getattr(cls, name)

    RecordMeta.__getattr__ = _meta_getattr  # type: ignore[method-assign]

    # When __info__ is explicitly set on a record class (e.g. for testing),
    # validate it through the C record setup path so invalid values still raise
    # TypeError before normal construction.
    _original_new = RecordBase.__new__

    def _compat_new(cls: Any, *args: Any, **kwargs: Any) -> Any:
        custom_info = cls.__dict__.get("__info__")
        if custom_info is not None and not args and not kwargs:
            private.record_setup_class(cls, custom_info)
        return _original_new(cls, *args, **kwargs)

    RecordBase.__new__ = _compat_new  # type: ignore[method-assign]

    _original_instance_getattr = RecordBase.__getattr__

    def _instance_getattr(self: Any, name: str) -> object:
        if name == "__info__":
            return getattr(type(self).gimeta, "info", None)
        return _original_instance_getattr(self, name)

    RecordBase.__getattr__ = _instance_getattr  # type: ignore[method-assign]

    # Register boxed classes under "native" profile too so that
    # pygi_class_registry_get_pytype_for_gtype() finds them when called from
    # C property getters (which have no namespace context, so profile defaults
    # to "native").
    _original_build_record = RecordBuilder.build_record

    def _build_record_compat(self: Any, info: Any) -> Any:
        from ginext.record import _record_classes_by_gtype

        cls = _original_build_record(self, info)
        gimeta = vars(cls).get("gimeta")
        if gimeta is None:
            return cls
        gtype_val = getattr(gimeta, "gtype", 0)
        profile = getattr(gimeta, "profile", None)
        if gtype_val and profile is not None and profile is not abi.NATIVE:
            info_obj = getattr(gimeta, "info", None)
            # Foreign types (e.g. cairo) use a dedicated conversion path in
            # gvalue.c (pygi_foreign_cairo_to_py); registering them under the
            # native profile would bypass that and return the wrong wrapper.
            if info_obj is not None and not getattr(info_obj, "is_foreign", lambda: False)():
                # Only register under native profile if no native class is
                # already registered — avoid overwriting native registration
                # when both native and compat tests run in the same worker.
                native_key = (abi.NATIVE.name, gtype_val)
                if _record_classes_by_gtype.get(native_key) is None:
                    original_profile = gimeta.profile
                    gimeta.profile = abi.NATIVE
                    try:
                        private.record_setup_class(cls, info_obj)
                    finally:
                        gimeta.profile = original_profile
        return cls

    RecordBuilder.build_record = _build_record_compat  # type: ignore[method-assign]
    RecordMeta._gi_compat_installed = True  # type: ignore[attr-defined]


def ensure_installed() -> None:
    """Apply all compat patches; idempotent and safe to call at any point
    after the gi package is fully initialized."""
    _install()
    _install_record_compat()
