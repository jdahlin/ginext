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

from __future__ import annotations

import pytest

from . import support

pytestmark = support.pytestmark


@pytest.mark.xfail(
    reason="concurrent private.invoke first use can race the descriptor cache",
    strict=True,
)
def test_concurrent_private_invoke_first_use_is_stable() -> None:
    code = r"""
import sys
import sysconfig
import threading

assert sysconfig.get_config_var("Py_GIL_DISABLED") == 1
assert not sys._is_gil_enabled()

from ginext import private

n_threads = 32
barrier = threading.Barrier(n_threads + 1)
errors = []
lock = threading.Lock()

def worker():
    try:
        barrier.wait()
        for _ in range(3000):
            private.invoke("GLib", "get_user_name")
            private.invoke("GLib", "get_real_name")
            private.invoke("GLib", "get_host_name")
    except BaseException as exc:
        with lock:
            errors.append(exc)

threads = [threading.Thread(target=worker) for _ in range(n_threads)]
for thread in threads:
    thread.start()
barrier.wait()
for thread in threads:
    thread.join()

if errors:
    raise errors[0]
"""
    proc = support.run_free_threaded_subprocess(code)
    assert proc.returncode == 0, proc.stderr or proc.stdout
