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

"""Port of goi/tests/test_log_set_writer_func.py."""

from __future__ import annotations

from typing import Any

import pytest


def _kick_log(GLib: Any) -> None:
    GLib.log_default_handler(
        "log-writer-test",
        GLib.LogLevelFlags.LEVEL_MESSAGE,
        "hello from test",
        None,
    )


@pytest.mark.subprocess(timeout=30)
def test_log_set_writer_func_no_user_data_current_shape() -> None:
    from ginext import GLib

    received: dict[str, Any] = {}

    def writer(level: Any, fields: Any) -> Any:
        received["nargs"] = 2
        return GLib.LogWriterOutput.HANDLED

    GLib.log_set_writer_func(writer)
    _kick_log(GLib)
    assert received.get("nargs") == 2, repr(received)


@pytest.mark.subprocess(timeout=30)
def test_log_set_writer_func_cambalache_shape() -> None:
    from ginext import GLib

    received: dict[str, Any] = {}

    def writer(level: Any, fields: Any, data: Any) -> Any:
        received["nargs"] = 3
        return GLib.LogWriterOutput.HANDLED

    GLib.log_set_writer_func(writer)
    _kick_log(GLib)
    assert received.get("nargs") == 3, repr(received)


@pytest.mark.subprocess(timeout=30)
def test_log_set_writer_func_with_user_data() -> None:
    from ginext import GLib

    received: dict[str, Any] = {}

    def writer(level: Any, fields: Any, user_data: Any) -> Any:
        received["nargs"] = 3
        received["user_data"] = user_data
        return GLib.LogWriterOutput.HANDLED

    GLib.log_set_writer_func(writer, "my_token")
    _kick_log(GLib)
    assert received.get("nargs") == 3, repr(received)
    assert received.get("user_data") == "my_token", repr(received)


@pytest.mark.subprocess(timeout=30)
def test_log_set_writer_func_with_user_data_on_bound_method() -> None:
    from ginext import GLib
    from ginext.gobject import gobjectclass as gobject

    class Holder(gobject.GObject):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[Any] = []
            GLib.log_set_writer_func(self._handler, "tag")

        def _handler(self, level: Any, fields: Any, data: Any) -> Any:
            self.calls.append((level, data))
            return GLib.LogWriterOutput.HANDLED

    holder = Holder()
    _kick_log(GLib)
    assert holder.calls, "writer never fired"
    assert holder.calls[0][1] == "tag", repr(holder.calls)
