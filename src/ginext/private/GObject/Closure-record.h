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

/* Closure ownership records. Shared bookkeeping between signal handlers,
 * GIR callback args, and other closure carriers. Holds source/owner/weak
 * targets via weak refs, the GSignal handler_id, and a state machine for
 * diagnostics. */
#ifndef GINEXT_CLOSURE_RECORD_H
#define GINEXT_CLOSURE_RECORD_H

#include "common.h"
#include "Closure.h"

typedef struct _PyGIClosureRecord PyGIClosureRecord;

typedef enum
{
  PYGI_CLOSURE_STATE_PENDING,
  PYGI_CLOSURE_STATE_CONNECTED,
  PYGI_CLOSURE_STATE_IN_FLIGHT,
  PYGI_CLOSURE_STATE_DISCONNECTING,
  PYGI_CLOSURE_STATE_DISCONNECTED,
  PYGI_CLOSURE_STATE_INVALIDATED,
  PYGI_CLOSURE_STATE_FINALIZED,
  PYGI_CLOSURE_STATE_CLASS_OWNED,
} PyGIClosureState;

PyGIClosureRecord *
pygi_closure_record_new (PyGIClosureRecordKind kind, PyObject *callable, PyObject *user_callable);

void
pygi_closure_record_free (PyGIClosureRecord *record);

void
pygi_closure_record_set_state (PyGIClosureRecord *record, PyGIClosureState state);

void
pygi_closure_record_invoke_begin (PyGIClosureRecord *record);

void
pygi_closure_record_invoke_end (PyGIClosureRecord *record);

void
pygi_closure_record_set_signal_metadata (PyGIClosureRecord *record,
                                         GObject *source,
                                         gulong handler_id,
                                         GObject *weak_target);

void
pygi_closure_record_set_owner (PyGIClosureRecord *record, GObject *owner);

gulong
pygi_closure_record_handler_id (PyGIClosureRecord *record);

void
pygi_closure_record_weak_target_finalized (PyGIClosureRecord *record, GObject *weak_target);

PyGIClosureRecord *
pygi_closure_record_new_inventory (PyGIClosureRecordKind kind,
                                   PyGIClosureState state,
                                   PyObject *callable,
                                   GObject *owner,
                                   GObject *source,
                                   GObject *weak_target);

guint
pygi_closure_records_disconnect_by_user_callable (GObject *instance, PyObject *callable);

gboolean
pygi_closure_records_set_signal_owner (GObject *instance, gulong handler_id, GObject *owner);

gboolean
pygi_closure_records_disconnect_signal (GObject *instance, gulong handler_id);

guint64
pygi_closure_records_signal_id (GObject *instance, gulong handler_id);

PyObject *
pygi_closure_records_list_py (void);

#endif /* GINEXT_CLOSURE_RECORD_H */
