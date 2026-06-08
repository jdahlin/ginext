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

from typing import Any

from . import Adw as Adw
from . import GIMarshallingTests as GIMarshallingTests
from . import GLib as GLib
from . import GModule as GModule
from . import GObject as GObject
from . import Gdk as Gdk
from . import GdkPixbuf as GdkPixbuf
from . import GIRepository as GIRepository
from . import Gio as Gio
from . import GioUnix as GioUnix
from . import GoiBench as GoiBench
from . import Graphene as Graphene
from . import Gsk as Gsk
from . import Gst as Gst
from . import GstApp as GstApp
from . import GstAudio as GstAudio
from . import GstBase as GstBase
from . import GstVideo as GstVideo
from . import Gtk as Gtk
from . import GtkSource as GtkSource
from . import HarfBuzz as HarfBuzz
from . import Pango as Pango
from . import PangoCairo as PangoCairo
from . import Regress as Regress
from . import RegressUnix as RegressUnix
from . import Vte as Vte
from . import WebKit as WebKit
from . import freetype2 as freetype2
from . import abi as abi
from . import defaults as defaults
from .namespace import Namespace as Namespace
from .signal.bound import Signal as Signal
from .signal.connection import (
    SignalConnection as SignalConnection,
    UnownedSignalHandlerWarning as UnownedSignalHandlerWarning,
)
from .signal.scoped import static_owner as static_owner

class PyGIWarning(Warning): ...
class PyGIDeprecationWarning(DeprecationWarning): ...

def _load_namespace(name: str, version: str, *, profile: Any = ...) -> Namespace: ...

def __getattr__(name: str) -> Any: ...
