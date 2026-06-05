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

"""ginext.__getattr__ is the only entry point for namespace access.

The plan: top-level access flows through resolve_version ->
require_namespace -> Namespace(...) -> cache on ginext.<Name>.
"""

from __future__ import annotations

import pytest


def test_attribute_access_returns_namespace() -> None:
    import ginext

    glib = ginext.GLib
    assert glib.__name__ == "GLib"


def test_namespace_has_version_attribute() -> None:
    from ginext import GLib

    assert GLib.__version__ == (2, 0)


def test_unknown_namespace_raises_attribute_error() -> None:
    import ginext

    with pytest.raises((AttributeError, ImportError)):
        ginext.NoSuchNamespaceXYZ


def test_attribute_access_consistent_with_from_import() -> None:
    import ginext
    from ginext import GLib

    assert ginext.GLib is GLib


def test_unknown_namespace_error_message_names_the_namespace() -> None:
    import ginext

    with pytest.raises((AttributeError, ImportError)) as excinfo:
        ginext.NoSuchNamespaceXYZ
    assert "NoSuchNamespaceXYZ" in str(excinfo.value)
