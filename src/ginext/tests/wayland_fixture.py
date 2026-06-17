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

from __future__ import annotations

import json
import os
import pathlib
import signal
import shutil
import subprocess
import tempfile
import time
from typing import Any, TypeGuard

import pytest


_STATE_ENV = "PYGIR_WAYLAND_STATE"
STATE = pathlib.Path(os.environ.get(_STATE_ENV, "/tmp/pytest-wayland.json"))
_PROC: subprocess.Popen[bytes] | None = None
_RUNTIME: str | None = None


def _load_state(state_path: pathlib.Path) -> dict[str, object] | None:
    try:
        state = json.loads(state_path.read_text())
    except FileNotFoundError, json.JSONDecodeError, OSError:
        return None
    if not isinstance(state, dict):
        return None
    return state


def _pid_is_running(pid: object) -> bool:
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _state_is_usable(state: dict[str, object] | None) -> TypeGuard[dict[str, object]]:
    if state is None:
        return False
    runtime = state.get("runtime")
    socket = state.get("socket")
    if not isinstance(runtime, str) or not isinstance(socket, str):
        return False
    if not _pid_is_running(state.get("pid")):
        return False
    return pathlib.Path(runtime, socket).exists()


def _apply_state(state: dict[str, object]) -> None:
    os.environ["XDG_RUNTIME_DIR"] = str(state["runtime"])
    os.environ["WAYLAND_DISPLAY"] = str(state["socket"])
    os.environ.setdefault("GDK_BACKEND", "wayland")


def _start_weston() -> tuple[subprocess.Popen[bytes], dict[str, str]]:
    global _RUNTIME

    STATE.unlink(missing_ok=True)
    runtime = tempfile.mkdtemp(prefix="wl-")
    _RUNTIME = runtime
    socket = "wayland-test"

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = runtime
    env["WAYLAND_DISPLAY"] = socket
    for key in (
        "ASAN_OPTIONS",
        "G_DEBUG",
        "G_SLICE",
        "LD_PRELOAD",
        "LSAN_OPTIONS",
        "MALLOC_CHECK_",
        "MALLOC_PERTURB_",
        "PYTHONMALLOC",
        "UBSAN_OPTIONS",
    ):
        env.pop(key, None)

    weston = shutil.which("weston")
    if weston is None:
        pytest.exit("weston is required for Wayland tests", returncode=4)

    proc = subprocess.Popen(
        [
            weston,
            "--backend=headless-backend.so",
            f"--socket={socket}",
            "--idle-time=0",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    path = pathlib.Path(runtime, socket)
    for _ in range(1000):
        if path.exists():
            break
        if proc.poll() is not None:
            break
        time.sleep(0.01)

    if not path.exists():
        proc.terminate()
        proc.wait()
        shutil.rmtree(runtime, ignore_errors=True)
        pytest.exit("weston did not create Wayland socket", returncode=4)

    STATE.write_text(
        json.dumps(
            {
                "runtime": runtime,
                "socket": socket,
                "pid": proc.pid,
            }
        )
    )

    os.environ[_STATE_ENV] = str(STATE)
    os.environ["XDG_RUNTIME_DIR"] = runtime
    os.environ["WAYLAND_DISPLAY"] = socket
    os.environ.setdefault("GDK_BACKEND", "wayland")

    return proc, os.environ.copy()


def _state_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get(_STATE_ENV, STATE))


def pytest_configure(config: pytest.Config) -> None:
    global _PROC

    state_path = _state_path()
    state = _load_state(state_path)
    if os.environ.get(_STATE_ENV) and _state_is_usable(state):
        _apply_state(state)
        return
    os.environ.pop(_STATE_ENV, None)

    # No Wayland compositor available (e.g. macOS or Windows): don't abort the
    # whole session. Wayland-dependent tests skip individually via the `wayland`
    # fixture instead.
    if shutil.which("weston") is None:
        return

    _PROC, _env = _start_weston()


def pytest_unconfigure(config: pytest.Config) -> None:
    global _PROC

    if _PROC is None:
        return
    _PROC.send_signal(signal.SIGTERM)
    _PROC.wait()
    _PROC = None
    _state_path().unlink(missing_ok=True)
    if _RUNTIME is not None:
        shutil.rmtree(_RUNTIME, ignore_errors=True)


@pytest.fixture(scope="session")
def wayland(worker_id: str) -> Any:
    global _PROC

    if shutil.which("weston") is None:
        pytest.skip("weston is not available on this platform")

    state_path = _state_path()
    state = _load_state(state_path)
    if not _state_is_usable(state):
        if worker_id in {"master", "gw0"}:
            _PROC, _env = _start_weston()
            state_path = _state_path()
            state = _load_state(state_path)
        else:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                state = _load_state(state_path)
                if _state_is_usable(state):
                    break
                time.sleep(0.01)
            else:
                pytest.exit(
                    "weston did not create a usable Wayland state", returncode=4
                )

    if not _state_is_usable(state):
        pytest.exit("weston did not create a usable Wayland state", returncode=4)
    _apply_state(state)

    env = os.environ.copy()

    yield env
