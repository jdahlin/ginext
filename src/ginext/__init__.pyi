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

# GI namespaces (GLib, Gtk, Gio, ...) are intentionally NOT declared here: they
# resolve to the installed `ginext-stubs` PEP 561 package so `from ginext import
# Gio` type-checks against real generated types. ginext's own library API stays
# inline-typed (this file, plus src/ginext/*.pyi like GIRepository.pyi).

def _load_namespace(name: str, version: str, *, profile: Any = ...) -> Namespace: ...

# GI namespaces are accessed via `from ginext import Ns` (PEP 561 resolution)
# for production code.  For dynamic attribute access (`import ginext;
# ginext.Ns`) used in some tests, fall back to Any.
def __getattr__(name: str) -> Any: ...
