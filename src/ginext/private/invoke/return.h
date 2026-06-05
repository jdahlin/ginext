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

/* Convert a finished GI invocation's return + OUT params to a single Python
 * value (or tuple). The slow FFI invoke path calls this after the C function
 * returns and before the IN-side cleanups fire, so the helper can read but
 * not free anything in the input arrays.
 *
 * Pairing logic:
 *   - C arrays (GI_ARRAY_TYPE_C) with a length param folded in alongside the
 *     buffer; the length slot is omitted from the visible tuple.
 *   - gboolean return + GError-throwing functions return only OUT params.
 *   - Otherwise the return value precedes the OUT params in a tuple. */

#include <Python.h>
#include "invoke/plan.h"
#include <girepository/girepository.h>

PyObject *
pygi_invoke_shape_return (GICallableInfo *cb,
                          const PyGIInvokePlan *plan,
                          PyObject *bound_self,
                          GIArgument *ret,
                          GITypeInfo **out_tis,
                          GIArgument *out_values,
                          size_t out_index,
                          const PyGIOutSlotPlan *out_slots,
                          const size_t *in_len_slot,
                          GITypeInfo *const *in_len_ti,
                          GIArgument *in_args);
