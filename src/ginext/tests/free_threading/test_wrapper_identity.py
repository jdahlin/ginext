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

import threading
from concurrent.futures import ThreadPoolExecutor


from . import support

pytestmark = support.pytestmark


def test_same_gobject_wrap_is_stable_across_threads() -> None:
    from ginext import Gio

    obj = Gio.Cancellable()
    n_threads = 16
    per_thread = 2000
    barrier = threading.Barrier(n_threads + 1)

    def worker() -> None:
        barrier.wait()
        for _ in range(per_thread):
            if not obj.is_bound():
                raise AssertionError("GObject wrapper became unbound")

    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = [executor.submit(worker) for _ in range(n_threads)]
        barrier.wait()
        for future in futures:
            future.result()
