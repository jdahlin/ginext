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
#include <glib-object.h>
#include <glib.h>

typedef enum
{
  PYGI_CLOSURE_RECORD_SIGNAL,
  PYGI_CLOSURE_RECORD_BINDING_TRANSFORM,
} PyGIClosureRecordKind;

void
pygi_callback_closure_destroy (gpointer closure);

void
pygi_callback_closure_set_py_user_data (gpointer closure, PyObject *user_data);

void
pygi_callback_closure_drain_deferred_frees (void);

int
pygi_callback_closure_new (PyObject *callable,
                           GIBaseInfo *callback_info,
                           GIScopeType scope,
                           GIArgument *dest,
                           PyGIArgCleanup *cleanup);

int
pygi_vfunc_closure_new (PyObject *callable,
                        GIBaseInfo *callback_info,
                        GIArgument *dest,
                        PyGIArgCleanup *cleanup);

GClosure *
pygi_closure_new (PyObject *callable);

GClosure *
pygi_closure_new_with_kind (PyObject *callable, PyGIClosureRecordKind kind);

GClosure *
pygi_closure_new_for_signal (PyObject *callable, GICallableInfo *signal_info);

GClosure *
pygi_closure_new_for_signal_full (PyObject *callable,
                                  PyObject *user_callable,
                                  GICallableInfo *signal_info,
                                  GObject *weak_target);

void
pygi_closure_set_signal_metadata (GClosure *closure,
                                  GObject *source,
                                  gulong handler_id,
                                  GObject *weak_target);

void
pygi_closure_set_once (GClosure *closure, gboolean once);

void
pygi_closure_set_signal_arg_limit (GClosure *closure, int signal_arg_limit);

void *
pygi_closure_get_record (GClosure *closure);

guint
pygi_closure_disconnect_by_callable (GObject *instance, PyObject *callable);
