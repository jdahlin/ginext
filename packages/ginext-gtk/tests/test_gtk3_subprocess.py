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

"""Run the Gtk-3 suite in one dedicated Gtk:3.0 subprocess.

Gtk 3 and Gtk 4 are process-global singletons that cannot coexist, so the gtk3/
tree is excluded from collection in the main (Gtk-4) workers (see
``pytest_ignore_collect`` in conftest.py) and executed here, in a child process
pinned to ``GINEXT_VERSIONS=Gtk:3.0``. This lets a single ``pytest`` /
``pytest -n auto`` invocation cover both Gtk major versions in one go, instead of
relying on a separate ``-m gtk3`` run.

This module must not import anything that pulls in Gtk at module level — it runs
inside the Gtk-4 process and only shells out.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
_GTK3_DIR = _TESTS_DIR / "gtk3"
_REPO_ROOT = _TESTS_DIR.parents[2]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Gtk 3 is not built on Windows (the vcpkg stack provides Gtk 4 only)",
)
@pytest.mark.timeout(360)
def test_gtk3_suite_runs_under_gtk3_in_subprocess() -> None:
    # Inside the gtk3 subprocess itself this module is not collected (only the
    # gtk3/ dir is), but guard anyway so the suite can never recurse into itself.
    if os.environ.get("PYGIR_GTK3_SUBPROCESS"):
        pytest.skip("already inside the gtk3 subprocess")
    # Under a debug / sanitizer build (both use the debug interpreter) running the
    # whole gtk3 suite in a child is impractically slow — it overruns the per-test
    # faulthandler timeout while the parent blocks in subprocess.run. gtk3 is a
    # compat-only surface already covered by the release `test` job, so skip it
    # here on debug builds.
    if hasattr(sys, "gettotalrefcount"):
        pytest.skip("gtk3 subprocess suite is too slow under a debug/sanitizer build")

    env = os.environ.copy()
    env["PYGIR_GTK3_SUBPROCESS"] = "1"
    env["GINEXT_VERSIONS"] = "Gtk:3.0"
    # The child runs serially in its own process; never let it inherit an xdist
    # worker identity that would change scheduling/reporting behaviour.
    env.pop("PYTEST_XDIST_WORKER", None)

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(_GTK3_DIR),
        "--rootdir",
        str(_REPO_ROOT),
        "-p",
        "no:cacheprovider",
        "-n",
        "0",
        "-q",
        "--no-header",
        "-o",
        "faulthandler_timeout=30",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    # Exit code 5 == "no tests collected" (e.g. Gtk 3 unavailable in this env).
    if proc.returncode == 5:
        pytest.skip("no Gtk-3 tests collected (Gtk 3 unavailable?)")
    if proc.returncode != 0:
        pytest.fail(
            "Gtk-3 subprocess suite failed "
            f"(exit {proc.returncode})\n\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
