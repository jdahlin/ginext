# Copyright 2026 Johan Dahlin
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

from __future__ import annotations

from gi.repository import Gio

# Re-export ginext's Gio classes so that gi.overrides.Gio.X == gi.repository.Gio.X,
# matching the identity guarantee PyGObject's override() machinery provides.
ActionMap = Gio.ActionMap
FileEnumerator = Gio.FileEnumerator
VolumeMonitor = Gio.VolumeMonitor
