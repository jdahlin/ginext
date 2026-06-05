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

/* Bind Python positional arguments into a GI invocation frame.
 * Uses the flag-based PyGIInvokePlan to skip closure/destroy companions,
 * handle deferred INOUT lengths, and pre-fill IN length placeholders. */

#include "runtime/callable.h"
#include "invoke/frame.h"
#include "invoke/plan.h"
#include <girepository/girepository.h>
#include <Python.h>
#include <stddef.h>

/* Bind all Python args (including self if descriptor->has_self) into frame.
 * Returns 0 on success; -1 on failure with Python error set.
 * On failure the frame is in a consistent state for pygi_invoke_frame_fail(). */
int
pygi_invoke_bind_args (PyGIMethodDescriptor *descriptor,
                       PyGIInvokeFrame *frame,
                       GICallableInfo *cb,
                       const PyGIInvokePlan *plan,
                       PyObject *const *args,
                       size_t nargs);
