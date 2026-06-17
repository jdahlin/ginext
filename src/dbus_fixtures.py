# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(scope="session")
def dbus_session_bus() -> Generator[str]:
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
