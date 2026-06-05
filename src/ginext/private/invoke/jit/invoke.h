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

/* Prepare/finish helpers for the full JIT direct-call path.
 *
 * The generated trampoline calls these around the target C function:
 *
 *   prepare_call -> loads ABI args -> call target -> store return -> finish_call
 *
 * prepare allocates the call frame on the heap, runs the binder, and
 * returns the frame pointer (or NULL on error with a Python exception
 * set). finish reads frame->ret + frame->out_args, raises GError if any,
 * shapes the Python return value, frees the frame, and returns the PyObject *.
 */

#include "invoke/frame.h"
#include "invoke/jit/plan.h"
#include <Python.h>

/* Compute the per-call arena size (16-byte aligned) for a callable
 * with the given GI arg count, in_args slots, and out_args slots.
 * The trampoline reserves this many bytes on its own stack and passes
 * a pointer to that scratch as the `scratch` argument to prepare. */
size_t
pygi_jit_arena_size_for (size_t n_gi_args, size_t max_in, size_t max_out);

/* `scratch` is a buffer of compiled->arena_size bytes the trampoline
 * reserved on its own stack. prepare lays out the frame and plan
 * storage in it; finish reads it back and runs cleanup. The buffer
 * lives until the trampoline returns, so finish does not free it. */
PyGIInvokeFrame *
pygi_jit_prepare_call (PyGICompiledCallable *compiled,
                       PyObject *const *args,
                       size_t nargs,
                       PyObject *kwnames,
                       void *scratch);

PyObject *
pygi_jit_finish_call (PyGICompiledCallable *compiled, PyGIInvokeFrame *frame);
