# Copyright 2026 Johan Dahlin
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

from __future__ import annotations

# signal_add_full was renamed to signal_add; declare it as a deprecated alias.
# _DEPRECATED_ATTRS is processed by gi.repository._apply_overrides to install
# a deprecating proxy around the namespace.
_DEPRECATED_ATTRS: dict[str, str] = {"signal_add_full": "signal_add"}

__all__: list[str] = []
