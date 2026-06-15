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

"""pygobject's `obj.props` property bag.

`obj.props.some_name` reads/writes the GObject property `some-name`. This is
pygobject's accessor shape, not ginext's native surface (declared properties are
plain attributes; introspected ones go through get_property/set_property), so
the proxy and the `props` property live in the compat package and are installed
onto the GObject class by `repository._install_gobject_props` when the
pygobject-compat layer is active.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from ginext.gobject.gobjectclass import GObject


def _list_properties(cls: type) -> list[Any]:
    from ginext.gobject.properties import PropertyInfo

    def _unwrap(result: list[Any]) -> list[Any]:
        return [p._pspec if isinstance(p, PropertyInfo) else p for p in result]

    try:
        result = cls.list_properties()  # type: ignore[attr-defined]
        return _unwrap(result)
    except Exception:
        try:
            from gi.repository import GObject

            return _unwrap(GObject.list_properties(cls))
        except Exception:
            try:
                gprops = getattr(cls, "__gproperties__", None)
                gimeta = getattr(cls, "gimeta", None)
                if isinstance(gprops, dict) and gimeta is not None:
                    result = []
                    for key in gprops:
                        pspec = gimeta.param_spec(key.replace("_", "-"))
                        if pspec is not None:
                            result.append(pspec)
                    return result
            except Exception:
                pass
            return []


class ClassPropsProxy:
    """Class-level props accessor: provides hasattr, iteration, and raises TypeError on set."""

    __slots__ = ("_cls",)

    def __init__(self, cls: type) -> None:
        object.__setattr__(self, "_cls", cls)

    def __getattr__(self, name: str) -> Any:
        from gi._gobject_compat_methods import _ParamSpecWrapper
        canon = name.replace("_", "-")
        for pspec in _list_properties(self._cls):
            if pspec.name == canon or pspec.name.replace("-", "_") == name:
                return _ParamSpecWrapper(pspec, owner_cls=self._cls)
        raise AttributeError(f"{self._cls.__name__} has no property {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        raise TypeError(
            f"cannot set property {name!r} on class {self._cls.__name__!r}; "
            "use an instance"
        )

    def __iter__(self) -> Iterator[Any]:
        return iter(_list_properties(self._cls))

    def __dir__(self) -> list[str]:
        return sorted(p.name.replace("-", "_") for p in _list_properties(self._cls))


class PropsProxy:
    __slots__ = ("_obj",)
    _obj: "GObject"

    def __init__(self, obj: "GObject") -> None:
        super().__setattr__("_obj", obj)

    def __getattr__(self, name: str) -> object:
        # Only compat propertyhelper descriptors with custom getters should
        # intercept props access. Native inherited pspec descriptors must keep
        # going through compat get_property() for coercion and wrapper policy.
        descriptor = type(self._obj).__dict__.get(name)
        if descriptor is not None and getattr(descriptor, "fget", None) is not None:
            from gi._propertyhelper import _CompatProperty

            if isinstance(descriptor, _CompatProperty):
                return descriptor.fget(self._obj)
        return self._obj.get_property(name)

    def __setattr__(self, name: str, value: object) -> None:
        # Match compat Object.set_property(): only compat propertyhelper
        # descriptors with custom getter/setter semantics bypass the generic
        # GObject property path.
        descriptor = type(self._obj).__dict__.get(name)
        if descriptor is not None and (
            getattr(descriptor, "fset", None) is not None
            or getattr(descriptor, "fget", None) is not None
        ):
            from gi._propertyhelper import _CompatProperty

            if isinstance(descriptor, _CompatProperty):
                type(descriptor).__set__(descriptor, self._obj, value)
                return
        self._obj.set_property(name, value)

    def __iter__(self) -> Iterator[Any]:
        return iter(_list_properties(type(self._obj)))

    def __dir__(self) -> list[str]:
        return sorted(p.name.replace("-", "_") for p in _list_properties(type(self._obj)))


class PropsDescriptor:
    """Descriptor that returns ClassPropsProxy for class access and PropsProxy for instances."""

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return ClassPropsProxy(objtype)  # type: ignore[arg-type]
        return PropsProxy(obj)


def install_props(gobject_cls: type) -> None:
    gobject_cls.props = PropsDescriptor()  # type: ignore[attr-defined]
