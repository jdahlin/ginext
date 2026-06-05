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
#include "invoke/arg-cleanup.h"

#include <girepository/girepository.h>
#include <glib.h>

PyObject *
pygi_ghash_to_py (GICallableInfo *cb, GITypeInfo *ti, GIArgument *arg, GITransfer transfer);

int
pygi_ghash_from_py (PyObject *value,
                    GITypeInfo *ti,
                    GITransfer transfer,
                    GIArgument *dest,
                    PyGIArgCleanup *cleanup);
