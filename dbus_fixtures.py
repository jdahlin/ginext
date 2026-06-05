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

"""Shared pytest fixtures for a self-contained private session D-Bus daemon.

Imported by the gio and gi-compat test conftests (which add the repo root to
``sys.path`` and ``from dbus_fixtures import dbus_session_bus``) so both suites
get an isolated session bus — without depending on the developer's real one,
and without ``Gio.TestDBus`` whose ``down()`` blocks ~30s on a cached
connection's weak-notify leak check.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(scope="session")
def dbus_session_bus() -> Generator[str, None, None]:
    """A private session ``dbus-daemon`` for the test session.

    Starts its own bus, points ``DBUS_SESSION_BUS_ADDRESS`` at it for the
    duration, and kills it at the end. Yields the bus address. Skips cleanly
    when ``dbus-daemon`` is not installed.
    """
    if shutil.which("dbus-daemon") is None:
        pytest.skip("dbus-daemon not available")

    proc = subprocess.Popen(
        ["dbus-daemon", "--session", "--nofork", "--print-address=1"],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    address = proc.stdout.readline().strip()
    if not address:
        proc.kill()
        proc.wait(timeout=5)
        pytest.skip("dbus-daemon did not report an address")

    previous = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
    try:
        yield address
    finally:
        if previous is None:
            os.environ.pop("DBUS_SESSION_BUS_ADDRESS", None)
        else:
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = previous
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
