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

from . import support

pytestmark = support.pytestmark


def test_concurrent_namespace_load_is_singleton() -> None:
    code = r"""
import sys
import sysconfig
import threading

assert sysconfig.get_config_var("Py_GIL_DISABLED") == 1
assert not sys._is_gil_enabled()

import ginext

n_threads = 32
barrier = threading.Barrier(n_threads + 1)
ids = []
errors = []
lock = threading.Lock()

def worker():
    try:
        barrier.wait()
        local = []
        for _ in range(1000):
            local.append(id(ginext._load_namespace("Gio", "2.0")))
        with lock:
            ids.extend(local)
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
unique_ids = set(ids)
if len(unique_ids) != 1:
    raise AssertionError(sorted(unique_ids))
"""
    proc = support.run_free_threaded_subprocess(code)
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_concurrent_namespace_first_access_builds_one_class_per_gtype() -> None:
    code = r"""
import sys
import sysconfig
import threading

assert sysconfig.get_config_var("Py_GIL_DISABLED") == 1
assert not sys._is_gil_enabled()

import ginext

Gio = ginext._load_namespace("Gio", "2.0")
names = ["Cancellable", "File", "SimpleAction", "ListStore", "Task"]
n_threads = 32
barrier = threading.Barrier(n_threads + 1)
ids_by_name = {name: [] for name in names}
errors = []
lock = threading.Lock()

def worker():
    try:
        barrier.wait()
        local = {}
        for _ in range(1000):
            for name in names:
                cls = getattr(Gio, name)
                local.setdefault(name, id(cls))
                if id(cls) != local[name]:
                    raise AssertionError((name, local[name], id(cls)))
        with lock:
            for name, ident in local.items():
                ids_by_name[name].append(ident)
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
for name, ids in ids_by_name.items():
    unique_ids = set(ids)
    if len(unique_ids) != 1:
        raise AssertionError((name, sorted(unique_ids)))
"""
    proc = support.run_free_threaded_subprocess(code)
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_concurrent_record_first_access_builds_one_class_per_gtype() -> None:
    code = r"""
import sys
import sysconfig
import threading

assert sysconfig.get_config_var("Py_GIL_DISABLED") == 1
assert not sys._is_gil_enabled()

import ginext

GLib = ginext._load_namespace("GLib", "2.0")
names = ["Variant", "Bytes", "DateTime", "Regex", "Uri"]
n_threads = 32
barrier = threading.Barrier(n_threads + 1)
ids_by_name = {name: [] for name in names}
errors = []
lock = threading.Lock()

def worker():
    try:
        barrier.wait()
        local = {}
        for _ in range(1000):
            for name in names:
                cls = getattr(GLib, name)
                local.setdefault(name, id(cls))
                if id(cls) != local[name]:
                    raise AssertionError((name, local[name], id(cls)))
        with lock:
            for name, ident in local.items():
                ids_by_name[name].append(ident)
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
for name, ids in ids_by_name.items():
    unique_ids = set(ids)
    if len(unique_ids) != 1:
        raise AssertionError((name, sorted(unique_ids)))
"""
    proc = support.run_free_threaded_subprocess(code)
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_concurrent_enum_first_access_builds_one_class_per_type() -> None:
    code = r"""
import sys
import sysconfig
import threading

assert sysconfig.get_config_var("Py_GIL_DISABLED") == 1
assert not sys._is_gil_enabled()

import ginext

GLib = ginext._load_namespace("GLib", "2.0")
names = [
    "FileTest",
    "OptionFlags",
    "RegexCompileFlags",
    "RegexMatchFlags",
    "UserDirectory",
    "ChecksumType",
    "IOCondition",
    "SpawnFlags",
]
n_threads = 32
barrier = threading.Barrier(n_threads + 1)
ids_by_name = {name: [] for name in names}
errors = []
lock = threading.Lock()

def worker():
    try:
        barrier.wait()
        local = {}
        for _ in range(1000):
            for name in names:
                cls = getattr(GLib, name)
                local.setdefault(name, id(cls))
                if id(cls) != local[name]:
                    raise AssertionError((name, local[name], id(cls)))
        with lock:
            for name, ident in local.items():
                ids_by_name[name].append(ident)
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
for name, ids in ids_by_name.items():
    unique_ids = set(ids)
    if len(unique_ids) != 1:
        raise AssertionError((name, sorted(unique_ids)))
"""
    proc = support.run_free_threaded_subprocess(code)
    assert proc.returncode == 0, proc.stderr or proc.stdout
