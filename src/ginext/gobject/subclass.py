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

"""Registration of Python-defined GObject subclasses.

`GObject.__init_subclass__` delegates here. This is the dual of `classbuild` —
where that module builds classes imported from a typelib, this one wires up a
`class MyObj(GObject): ...` written in Python: it installs declared properties,
allocates the GType, inherits the parent's signal tables, and registers any
`GObject.Signal()` descriptors. Classes that `ClassBuilder` already populated
(detected via ``"gimeta" in cls.__dict__``) skip the registration path.

Kept out of `gobjectclass` so the GObject class definition reads as behaviour,
not construction. The only `GObject` reference is the root-class identity check,
imported lazily at call time (this runs at class-creation, well after import),
so there is no import cycle with `gobjectclass`.
"""

from __future__ import annotations

import annotationlib
from typing import TYPE_CHECKING, Any, cast

from .. import abi, features, private
from ..signal.descriptor import SignalDescriptor as Signal
from .properties import (
    PropertyBase,
    _is_gtype_value_type,
    coerce_property_default,
    property_value_type,
    resolve_annotations,
    validate_pygobject_property_metadata,
)
from .resolve import classbuild_module, gobject_repo, own_gimeta

if TYPE_CHECKING:
    from .gobjectclass import GObject


def _own_annotations(cls: type) -> dict[str, object]:
    return annotationlib.get_annotations(cls)


def _install_extension_metadata(cls: type) -> None:
    gtk_actions: list[object] = []
    for attr in cls.__dict__.values():
        spec = getattr(attr, "gimeta_action", None)
        if spec is not None:
            gtk_actions.append(spec)
    if gtk_actions:
        gimeta = cast("Any", cls.gimeta)
        bucket = gimeta.extensions.setdefault("Gtk", {})
        if isinstance(bucket, dict):
            bucket["actions"] = gtk_actions


def register_python_subclass(cls: type[GObject], *, type_name: str | None) -> None:
    from .gobjectclass import GObject

    # ClassBuilder pre-populates gimeta + signal tables for imported
    # classes. Detect that path and skip the Python-defined-subclass
    # registration entirely.
    already_built = "gimeta" in cls.__dict__

    if not already_built:
        if features.is_enabled(features.PYGOBJECT_COMPAT):
            validate_pygobject_property_metadata(cls)

    annotations = resolve_annotations(_own_annotations(cls))
    declared_properties = {
        attr_name: attr
        for attr_name, attr in cls.__dict__.items()
        if isinstance(attr, PropertyBase)
    }
    if not already_built:
        for attr_name, attr in declared_properties.items():
            if attr.type is not None:
                annotations.setdefault(attr_name, attr.type)
        for attr_name, attr in declared_properties.items():
            value_type = annotations.get(attr_name)
            if value_type is not None:
                value_type = property_value_type(value_type)
                annotations[attr_name] = value_type
                attr.type = cast("type[Any] | None", value_type)
                coerce_property_default(value_type, attr)

    if not already_built:
        requested_type_name = type_name
        if requested_type_name is None and features.is_enabled(
            features.PYGOBJECT_COMPAT
        ):
            compat_type_name = cls.__dict__.get("__gtype_name__")
            if isinstance(compat_type_name, str) and compat_type_name:
                requested_type_name = compat_type_name
        cls.gimeta = private.GIMeta.register_subclass(
            cls,
            annotations,
            requested_type_name or f"{cls.__module__}+{cls.__name__}".replace(".", "+"),
        )
        cls.gimeta.profile = (
            abi.PYGOBJECT
            if features.is_enabled(features.PYGOBJECT_COMPAT)
            else abi.NATIVE
        )
        classbuild_module().register_class_for_gtype(cls)
        gimeta = cast("Any", cls.gimeta)
        for attr_name, attr in declared_properties.items():
            setattr(
                cls,
                attr_name,
                private.PropertyDescriptor.from_spec(
                    attr,
                    cls,
                    gimeta.prop_ids[attr_name],
                    gimeta.pspecs[attr_name],
                    _is_gtype_value_type(attr.type),
                ),
            )

    if not cls.gimeta.signal_infos:
        parent_cls = cls.__bases__[0]
        parent_gimeta = own_gimeta(parent_cls)
        signal_infos = {} if parent_gimeta is None else parent_gimeta.signal_infos
        method_backings = (
            {} if parent_gimeta is None else parent_gimeta.signal_method_backings
        )
        vfunc_infos = {} if parent_gimeta is None else parent_gimeta.vfunc_infos
        cls.gimeta.signal_infos = dict(signal_infos)
        cls.gimeta.signal_method_backings = dict(method_backings)
        cls.gimeta.vfunc_infos = dict(vfunc_infos)
        # Python-defined subclasses whose nearest Python ancestor is
        # the root `GObject` won't see notify / other GObject base
        # signals through MRO (the root's table is empty until
        # ClassBuilder builds the imported GObject.Object). Merge
        # those in once on first Python subclass init.
        if not already_built and parent_cls is GObject:
            obj_cls = gobject_repo().Object
            for k, v in obj_cls.gimeta.signal_infos.items():
                cls.gimeta.signal_infos.setdefault(k, v)
            for k, v in obj_cls.gimeta.signal_method_backings.items():
                cls.gimeta.signal_method_backings.setdefault(k, v)
            for k, v in obj_cls.gimeta.vfunc_infos.items():
                cls.gimeta.vfunc_infos.setdefault(k, v)

    # Register Python-defined signal descriptors. ClassBuilder-built
    # classes don't have SignalDescriptor instances in their dict, so
    # this is a no-op there.
    for attr_name, attr in list(cls.__dict__.items()):
        if isinstance(attr, Signal):
            if attr._is_imported:
                continue
            attr._register(cls.gimeta)
            cls.gimeta.signal_infos[attr_name] = attr

    if not already_built and features.is_enabled(features.PYGOBJECT_COMPAT):
        try:
            from gi._signalhelper import iter_pygobject_signal_descriptors
        except ImportError:
            pass
        else:
            for attr_name, sd in iter_pygobject_signal_descriptors(cls):
                sd._register(cls.gimeta)
                cls.gimeta.signal_infos[attr_name] = sd

    if not already_built:
        _surface_inherited_properties(cls, annotations)
        _install_extension_metadata(cls)


def _surface_inherited_properties(
    cls: type[GObject], declared: dict[str, object]
) -> None:
    """Advertise every GObject property — the class's own plus those inherited
    from a native base — as a field on a Python-defined subclass: install a
    descriptor and an ``__annotations__`` entry for each property the class
    didn't already declare (dataclass-subclass style). Imported typelib classes
    skip this and resolve properties lazily on first attribute access instead.

    ``declared`` seeds ``__annotations__`` with the subclass's own annotated
    fields, which on 3.14 live in ``__annotate__`` rather than a real dict — so
    setting an explicit dict here must preserve them, not shadow them.
    """
    from .gobjectclass import _synthesize_pspec_property

    cls.__annotations__ = dict(declared)
    # Reserve names the subclass explicitly owns, plus inherited properties
    # that are owned by a Python ancestor's own pspec table. Imported native
    # bases may have lazily cached property descriptors in their __dict__ from
    # earlier accesses; those should not block the subclass from surfacing the
    # inherited property up front.
    taken = set(vars(cls))
    taken.update(cls.gimeta.signal_infos)
    inherited_python_properties = set()
    for base in cls.__mro__[1:]:
        try:
            inherited_python_properties.update(own_gimeta(base).pspecs)
        except AttributeError:
            pass
    for prop_name in cls.gimeta.list_property_names():
        py_name = prop_name.replace("-", "_")
        if py_name not in taken and py_name not in inherited_python_properties:
            _synthesize_pspec_property(cls, py_name)
