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

/* IN-side conversion of a Python sequence to a heap-allocated C array.
 * OUT-side conversion of a heap-allocated C array to a Python list.
 *
 * Built for the slow GI invoke path. The element converter is dispatched on
 * elem_ti's tag: strings, primitives, GValue, struct/union, object/interface,
 * GVariant, nested arrays. The GArray/GPtrArray/GByteArray containers use a
 * different entrypoint (see array.h). */

#include <Python.h>
#include <girepository/girepository.h>

#include "invoke/arg-cleanup.h"

/* Convert Python value `h` to a C array referenced by `array_arg->v_pointer`.
 * If `len_ti != NULL`, also writes the element count into `*len_arg` using
 * `len_ti`'s integer tag.  If `zero_terminated` is true, appends a zero
 * element to the allocation.  Registers a cleanup record describing how to free
 * the new allocation after the call.  Returns 0 on success, -1 with a Python
 * exception on failure. */
int
pygi_py_to_c_array_invoke (PyObject *h,
                           GITypeInfo *elem_ti,
                           GIArgument *array_arg,
                           GIArgument *len_arg,
                           GITypeInfo *len_ti,
                           gboolean zero_terminated,
                           gsize fixed_size,
                           PyGIArgCleanup *cleanup,
                           GITransfer transfer);

/* Convert a C array (pointer + length) to a Python list or bytes.
 * `len_ti` and `len_arg` provide the element count; if they describe a
 * zero-terminated array the count is ignored. */
PyObject *
pygi_c_array_to_py (GICallableInfo *cb,
                    GITypeInfo *ti,
                    GIArgument *arg,
                    GITypeInfo *len_ti,
                    GIArgument *len_arg,
                    GITransfer transfer);
