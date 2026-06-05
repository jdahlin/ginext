/* Copyright 2026 Johan Dahlin
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#pragma once

#include <Python.h>
#include <girepository/girepository.h>

/* Extract a GIBaseInfo* from a native GIRepository.*Info instance.
 * Returns NULL with a TypeError set if obj is not such an instance. */
GIBaseInfo *
gi_info_from_py (PyObject *obj);

/* Same as gi_info_from_py but treats NULL and Py_None as "no info"
 * rather than an error; returns NULL without setting an error in that case. */
GIBaseInfo *
gi_info_from_py_or_none (PyObject *obj);

/* Wrap a GIBaseInfo* as its native GIRepository.*Info type. The wrapper
 * acquires its own ref; NULL maps to None. */
PyObject *
gi_info_to_py (GIBaseInfo *info);

/* Like gi_info_to_py, but consumes a transfer-full info (releases the caller's
 * ref after the wrapper takes its own). For the gi_*_get_* getters that return
 * an owned GIBaseInfo*. NULL maps to None. */
PyObject *
gi_info_to_py_owned (GIBaseInfo *info);
