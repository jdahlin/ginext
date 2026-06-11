# Copyright 2026 Johan Dahlin
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

from __future__ import annotations

import warnings

from gi import PyGIWarning
from gi.repository import Gio

# Re-export ginext's Gio classes so that gi.overrides.Gio.X == gi.repository.Gio.X,
# matching the identity guarantee PyGObject's override() machinery provides.
ActionMap = Gio.ActionMap
FileEnumerator = Gio.FileEnumerator
VolumeMonitor = Gio.VolumeMonitor


_DBUS_STRUCT_WARN = (
    "Positional/keyword construction is deprecated, "
    "please use keyword arguments only"
)


def _make_dbus_warn_class(base: type) -> type:
    """Create a subclass of a DBus info struct that warns on construction."""

    class _WarnInit(base):  # type: ignore[valid-type]
        def __init__(self, *args: object, **kwargs: object) -> None:
            warnings.warn(_DBUS_STRUCT_WARN, PyGIWarning, stacklevel=2)
            super().__init__(*args, **kwargs)

    _WarnInit.__name__ = base.__name__
    _WarnInit.__qualname__ = base.__qualname__
    return _WarnInit


DBusAnnotationInfo = _make_dbus_warn_class(Gio.DBusAnnotationInfo)
DBusArgInfo = _make_dbus_warn_class(Gio.DBusArgInfo)
DBusMethodInfo = _make_dbus_warn_class(Gio.DBusMethodInfo)
DBusSignalInfo = _make_dbus_warn_class(Gio.DBusSignalInfo)
DBusInterfaceInfo = _make_dbus_warn_class(Gio.DBusInterfaceInfo)
DBusNodeInfo = _make_dbus_warn_class(Gio.DBusNodeInfo)

__all__ = [
    "ActionMap",
    "DBusAnnotationInfo",
    "DBusArgInfo",
    "DBusInterfaceInfo",
    "DBusMethodInfo",
    "DBusNodeInfo",
    "DBusSignalInfo",
    "FileEnumerator",
    "VolumeMonitor",
]
