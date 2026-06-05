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

"""Out-of-scope arg/return types must be rejected at descriptor build
time (i.e. when the method is first looked up), not at call time.

The plan: "if an unsupported path still needs GI metadata at call time,
mark that path as not optimized and add tests so it cannot silently
become the normal path."
"""

from __future__ import annotations


def test_gvariant_return_method_builds_descriptor() -> None:
    import ginext

    desc = ginext.Gio.Settings.get_value

    assert callable(desc)
    assert getattr(desc, "_pygi_unsupported_for_test", None) is None


def test_interface_method_builds_descriptor() -> None:
    import ginext

    desc = ginext.Gio.File.query_info

    assert callable(desc)
    assert getattr(desc, "_pygi_unsupported_for_test", None) is None
