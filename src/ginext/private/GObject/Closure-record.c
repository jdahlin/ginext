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

/* Closure ownership records (ported from src/goi/_goi/GObject/Closure-record.c).
 * Tracks source/owner/weak_target via GObject weak refs, the GSignal
 * handler_id, and a state machine. Used by the signal GClosure subclass and
 * (later) by GIR callback-arg closures. */
#include "Closure-record.h"

#include "Object.h"

struct _PyGIClosureRecord
{
  guint64 id;
  PyGIClosureRecordKind kind;
  PyGIClosureState state;
  guint in_flight;
  gint64 created_at_us;
  gint64 state_changed_at_us;
  gint64 last_invoked_at_us;
  GObject *source; /* non-owning */
  GObject *owner; /* non-owning */
  GObject *weak_target; /* non-owning, cleared from weak-notify */
  gulong handler_id;
  gboolean source_weak_installed;
  gboolean owner_weak_installed;
  gboolean weak_target_weak_installed;
  PyObject *callable; /* borrowed unless owns_callable */
  PyObject *user_callable; /* borrowed unless owns_user_callable */
  gboolean owns_callable;
  gboolean owns_user_callable;
};

static GMutex records_mutex;
static GPtrArray *records;
static guint64 next_record_id = 1;

static void
ensure_records_locked (void)
{
  if (records == NULL)
    records = g_ptr_array_new ();
}

static const char *
kind_to_string (PyGIClosureRecordKind kind)
{
  switch (kind)
    {
    case PYGI_CLOSURE_RECORD_SIGNAL:
      return "signal";
    case PYGI_CLOSURE_RECORD_BINDING_TRANSFORM:
      return "binding-transform";
    }
  return "unknown";
}

static const char *
carrier_to_string (PyGIClosureRecordKind kind)
{
  switch (kind)
    {
    case PYGI_CLOSURE_RECORD_SIGNAL:
    case PYGI_CLOSURE_RECORD_BINDING_TRANSFORM:
      return "gclosure";
    }
  return "unknown";
}

static const char *
state_to_string (PyGIClosureState state)
{
  switch (state)
    {
    case PYGI_CLOSURE_STATE_PENDING:
      return "pending";
    case PYGI_CLOSURE_STATE_CONNECTED:
      return "connected";
    case PYGI_CLOSURE_STATE_IN_FLIGHT:
      return "in-flight";
    case PYGI_CLOSURE_STATE_DISCONNECTING:
      return "disconnecting";
    case PYGI_CLOSURE_STATE_DISCONNECTED:
      return "disconnected";
    case PYGI_CLOSURE_STATE_INVALIDATED:
      return "invalidated";
    case PYGI_CLOSURE_STATE_FINALIZED:
      return "finalized";
    case PYGI_CLOSURE_STATE_CLASS_OWNED:
      return "class-owned";
    }
  return "unknown";
}

static PyObject *
object_or_none (GObject *object)
{
  if (object == NULL)
    Py_RETURN_NONE;
  if (pygi_gobject_type == NULL)
    Py_RETURN_NONE;
  return pygi_gobject_new ((PyObject *)pygi_gobject_type, object, 0);
}

static int
dict_set_newref (PyObject *dict, const char *key, PyObject *value)
{
  if (value == NULL)
    return -1;
  int result = PyDict_SetItemString (dict, key, value);
  Py_DECREF (value);
  return result;
}

static void
pygi_closure_record_source_weak_notify (gpointer data, GObject *where_the_object_was);
static void
pygi_closure_record_owner_weak_notify (gpointer data, GObject *where_the_object_was);
static void
pygi_closure_record_weak_target_weak_notify (gpointer data, GObject *where_the_object_was);
static gboolean
pygi_closure_record_disconnect (PyGIClosureRecord *record);

static void
pygi_closure_record_clear_weak_edges (PyGIClosureRecord *record)
{
  if (record == NULL)
    return;

  if (record->source_weak_installed && record->source != NULL)
    {
      g_object_weak_unref (record->source, pygi_closure_record_source_weak_notify, record);
      record->source_weak_installed = FALSE;
    }
  if (record->owner_weak_installed && record->owner != NULL)
    {
      g_object_weak_unref (record->owner, pygi_closure_record_owner_weak_notify, record);
      record->owner_weak_installed = FALSE;
    }
  if (record->weak_target_weak_installed && record->weak_target != NULL)
    {
      g_object_weak_unref (record->weak_target,
                           pygi_closure_record_weak_target_weak_notify,
                           record);
      record->weak_target_weak_installed = FALSE;
    }
  record->source = NULL;
  record->owner = NULL;
  record->weak_target = NULL;
}

static void
pygi_closure_record_source_weak_notify (gpointer data, GObject *where_the_object_was)
{
  (void)where_the_object_was;
  PyGIClosureRecord *record = (PyGIClosureRecord *)data;
  record->source = NULL;
  record->source_weak_installed = FALSE;
  record->handler_id = 0;
  if (record->state != PYGI_CLOSURE_STATE_FINALIZED)
    pygi_closure_record_set_state (record, PYGI_CLOSURE_STATE_INVALIDATED);
}

static void
pygi_closure_record_owner_weak_notify (gpointer data, GObject *where_the_object_was)
{
  (void)where_the_object_was;
  PyGIClosureRecord *record = (PyGIClosureRecord *)data;
  record->owner = NULL;
  record->owner_weak_installed = FALSE;
  pygi_closure_record_disconnect (record);
}

static void
pygi_closure_record_weak_target_weak_notify (gpointer data, GObject *where_the_object_was)
{
  (void)where_the_object_was;
  PyGIClosureRecord *record = (PyGIClosureRecord *)data;
  record->weak_target = NULL;
  record->weak_target_weak_installed = FALSE;
  if (record->state == PYGI_CLOSURE_STATE_CONNECTED)
    pygi_closure_record_set_state (record, PYGI_CLOSURE_STATE_INVALIDATED);
}

PyGIClosureRecord *
pygi_closure_record_new (PyGIClosureRecordKind kind, PyObject *callable, PyObject *user_callable)
{
  PyGIClosureRecord *record = g_new0 (PyGIClosureRecord, 1);
  record->kind = kind;
  record->state = PYGI_CLOSURE_STATE_PENDING;
  record->created_at_us = g_get_real_time ();
  record->state_changed_at_us = record->created_at_us;
  record->last_invoked_at_us = 0;
  record->callable = callable;
  record->user_callable = user_callable != NULL ? user_callable : callable;
  if (user_callable != NULL && user_callable != callable)
    {
      Py_INCREF (user_callable);
      record->owns_user_callable = TRUE;
    }

  g_mutex_lock (&records_mutex);
  ensure_records_locked ();
  record->id = next_record_id++;
  g_ptr_array_add (records, record);
  g_mutex_unlock (&records_mutex);

  return record;
}

void
pygi_closure_record_free (PyGIClosureRecord *record)
{
  if (record == NULL)
    return;

  pygi_closure_record_clear_weak_edges (record);

  g_mutex_lock (&records_mutex);
  if (records != NULL)
    g_ptr_array_remove_fast (records, record);
  g_mutex_unlock (&records_mutex);

  if (record->owns_callable)
    Py_CLEAR (record->callable);
  else
    record->callable = NULL;
  if (record->owns_user_callable)
    Py_CLEAR (record->user_callable);
  else
    record->user_callable = NULL;
  g_free (record);
}

void
pygi_closure_record_set_state (PyGIClosureRecord *record, PyGIClosureState state)
{
  if (record == NULL)
    return;
  if (record->state != state)
    {
      record->state = state;
      record->state_changed_at_us = g_get_real_time ();
    }
}

void
pygi_closure_record_invoke_begin (PyGIClosureRecord *record)
{
  if (record == NULL)
    return;
  record->in_flight++;
  record->last_invoked_at_us = g_get_real_time ();
  record->state = PYGI_CLOSURE_STATE_IN_FLIGHT;
  record->state_changed_at_us = record->last_invoked_at_us;
}

void
pygi_closure_record_invoke_end (PyGIClosureRecord *record)
{
  if (record == NULL)
    return;
  if (record->in_flight > 0)
    record->in_flight--;
  if (record->state == PYGI_CLOSURE_STATE_IN_FLIGHT && record->in_flight == 0)
    {
      record->state = PYGI_CLOSURE_STATE_CONNECTED;
      record->state_changed_at_us = g_get_real_time ();
    }
}

gulong
pygi_closure_record_handler_id (PyGIClosureRecord *record)
{
  return record != NULL ? record->handler_id : 0;
}

void
pygi_closure_record_set_signal_metadata (PyGIClosureRecord *record,
                                         GObject *source,
                                         gulong handler_id,
                                         GObject *weak_target)
{
  if (record == NULL)
    return;
  if (record->source_weak_installed && record->source != source && record->source != NULL)
    {
      g_object_weak_unref (record->source, pygi_closure_record_source_weak_notify, record);
      record->source_weak_installed = FALSE;
    }
  record->source = source;
  record->handler_id = handler_id;
  record->weak_target = weak_target;
  if (source != NULL && !record->source_weak_installed)
    {
      g_object_weak_ref (source, pygi_closure_record_source_weak_notify, record);
      record->source_weak_installed = TRUE;
    }
  if (handler_id != 0)
    pygi_closure_record_set_state (record, PYGI_CLOSURE_STATE_CONNECTED);
}

void
pygi_closure_record_set_owner (PyGIClosureRecord *record, GObject *owner)
{
  if (record == NULL)
    return;
  if (record->owner_weak_installed && record->owner != owner && record->owner != NULL)
    {
      g_object_weak_unref (record->owner, pygi_closure_record_owner_weak_notify, record);
      record->owner_weak_installed = FALSE;
    }
  record->owner = owner;
  if (owner != NULL && !record->owner_weak_installed)
    {
      g_object_weak_ref (owner, pygi_closure_record_owner_weak_notify, record);
      record->owner_weak_installed = TRUE;
    }
}

static gboolean
pygi_closure_record_disconnect (PyGIClosureRecord *record)
{
  if (record == NULL)
    return FALSE;

  GObject *source = record->source;
  gulong handler_id = record->handler_id;
  if (source == NULL || handler_id == 0)
    {
      if (record->state != PYGI_CLOSURE_STATE_FINALIZED)
        pygi_closure_record_set_state (record, PYGI_CLOSURE_STATE_INVALIDATED);
      return FALSE;
    }

  g_object_ref (source);
  record->handler_id = 0;
  pygi_closure_record_set_state (record, PYGI_CLOSURE_STATE_DISCONNECTING);
  gboolean connected = g_signal_handler_is_connected (source, handler_id);
  if (connected)
    g_signal_handler_disconnect (source, handler_id);
  g_object_unref (source);
  return connected;
}

static void
pygi_closure_record_clear_weak_target (PyGIClosureRecord *record)
{
  if (record == NULL)
    return;
  if (record->weak_target_weak_installed && record->weak_target != NULL)
    {
      g_object_weak_unref (record->weak_target,
                           pygi_closure_record_weak_target_weak_notify,
                           record);
      record->weak_target_weak_installed = FALSE;
    }
  record->weak_target = NULL;
  if (record->state == PYGI_CLOSURE_STATE_CONNECTED)
    pygi_closure_record_set_state (record, PYGI_CLOSURE_STATE_DISCONNECTING);
}

static void
pygi_closure_record_set_inventory_weak_target (PyGIClosureRecord *record, GObject *weak_target)
{
  if (record == NULL)
    return;
  pygi_closure_record_clear_weak_target (record);
  record->weak_target = weak_target;
  if (weak_target != NULL)
    {
      g_object_weak_ref (weak_target, pygi_closure_record_weak_target_weak_notify, record);
      record->weak_target_weak_installed = TRUE;
    }
}

void
pygi_closure_record_weak_target_finalized (PyGIClosureRecord *record, GObject *weak_target)
{
  if (record == NULL)
    return;

  record->weak_target = NULL;
  if (record->weak_target_weak_installed)
    record->weak_target_weak_installed = FALSE;

  if (record->source == weak_target)
    {
      record->source = NULL;
      record->source_weak_installed = FALSE;
      record->handler_id = 0;
      if (record->state != PYGI_CLOSURE_STATE_FINALIZED)
        pygi_closure_record_set_state (record, PYGI_CLOSURE_STATE_INVALIDATED);
      return;
    }

  pygi_closure_record_disconnect (record);
}

PyGIClosureRecord *
pygi_closure_record_new_inventory (PyGIClosureRecordKind kind,
                                   PyGIClosureState state,
                                   PyObject *callable,
                                   GObject *owner,
                                   GObject *source,
                                   GObject *weak_target)
{
  PyGIClosureRecord *record = pygi_closure_record_new (kind, callable, callable);
  if (callable != NULL)
    {
      Py_INCREF (callable);
      record->owns_callable = TRUE;
    }
  pygi_closure_record_set_owner (record, owner);
  pygi_closure_record_set_signal_metadata (record, source, 0, NULL);
  pygi_closure_record_set_inventory_weak_target (record, weak_target);
  pygi_closure_record_set_state (record, state);
  return record;
}

static PyGIClosureRecord *
pygi_closure_records_find_signal_locked (GObject *instance, gulong handler_id)
{
  if (records == NULL)
    return NULL;
  for (guint i = 0; i < records->len; i++)
    {
      PyGIClosureRecord *record = g_ptr_array_index (records, i);
      if (record->kind == PYGI_CLOSURE_RECORD_SIGNAL && record->source == instance
          && record->handler_id == handler_id)
        return record;
    }
  return NULL;
}

guint
pygi_closure_records_disconnect_by_user_callable (GObject *instance, PyObject *callable)
{
  guint disconnected = 0;
  GArray *handler_ids = g_array_new (FALSE, FALSE, sizeof (gulong));

  g_mutex_lock (&records_mutex);
  if (records != NULL)
    {
      for (guint i = 0; i < records->len; i++)
        {
          PyGIClosureRecord *record = g_ptr_array_index (records, i);
          if (record->kind != PYGI_CLOSURE_RECORD_SIGNAL)
            continue;
          if (record->source != instance)
            continue;
          if (record->user_callable != callable)
            continue;
          if (record->handler_id == 0)
            continue;
          pygi_closure_record_set_state (record, PYGI_CLOSURE_STATE_DISCONNECTING);
          g_array_append_val (handler_ids, record->handler_id);
        }
    }
  g_mutex_unlock (&records_mutex);

  for (guint i = 0; i < handler_ids->len; i++)
    {
      gulong handler_id = g_array_index (handler_ids, gulong, i);
      g_signal_handler_disconnect (instance, handler_id);
      disconnected++;
    }

  g_array_unref (handler_ids);
  return disconnected;
}

gboolean
pygi_closure_records_set_signal_owner (GObject *instance, gulong handler_id, GObject *owner)
{
  PyGIClosureRecord *record = NULL;
  g_mutex_lock (&records_mutex);
  record = pygi_closure_records_find_signal_locked (instance, handler_id);
  g_mutex_unlock (&records_mutex);
  if (record == NULL)
    return FALSE;
  pygi_closure_record_set_owner (record, owner);
  return TRUE;
}

GObject *
pygi_closure_record_owner (PyGIClosureRecord *record)
{
  return record != NULL ? record->owner : NULL;
}

gboolean
pygi_closure_records_disconnect_signal (GObject *instance, gulong handler_id)
{
  PyGIClosureRecord *record = NULL;
  g_mutex_lock (&records_mutex);
  record = pygi_closure_records_find_signal_locked (instance, handler_id);
  g_mutex_unlock (&records_mutex);
  if (record == NULL)
    return FALSE;
  return pygi_closure_record_disconnect (record);
}

guint64
pygi_closure_records_signal_id (GObject *instance, gulong handler_id)
{
  guint64 id = 0;
  g_mutex_lock (&records_mutex);
  PyGIClosureRecord *record = pygi_closure_records_find_signal_locked (instance, handler_id);
  if (record != NULL)
    id = record->id;
  g_mutex_unlock (&records_mutex);
  return id;
}

PyObject *
pygi_closure_records_list_py (void)
{
  PyObject *list = PyList_New (0);
  if (list == NULL)
    return NULL;

  g_mutex_lock (&records_mutex);
  if (records != NULL)
    {
      for (guint i = 0; i < records->len; i++)
        {
          PyGIClosureRecord *record = g_ptr_array_index (records, i);
          PyObject *dict = PyDict_New ();
          if (dict == NULL)
            goto error_locked;

          if (dict_set_newref (dict, "id", PyLong_FromUnsignedLongLong (record->id)) < 0
              || dict_set_newref (dict,
                                  "kind",
                                  PyUnicode_FromString (kind_to_string (record->kind)))
                     < 0
              || dict_set_newref (dict,
                                  "carrier",
                                  PyUnicode_FromString (carrier_to_string (record->kind)))
                     < 0
              || dict_set_newref (dict,
                                  "state",
                                  PyUnicode_FromString (state_to_string (record->state)))
                     < 0
              || dict_set_newref (dict, "in_flight", PyLong_FromUnsignedLong (record->in_flight))
                     < 0
              || dict_set_newref (dict,
                                  "created_at_us",
                                  PyLong_FromLongLong (record->created_at_us))
                     < 0
              || dict_set_newref (dict,
                                  "state_changed_at_us",
                                  PyLong_FromLongLong (record->state_changed_at_us))
                     < 0
              || dict_set_newref (dict,
                                  "last_invoked_at_us",
                                  PyLong_FromLongLong (record->last_invoked_at_us))
                     < 0
              || dict_set_newref (dict, "source", object_or_none (record->source)) < 0
              || dict_set_newref (dict, "owner", object_or_none (record->owner)) < 0
              || dict_set_newref (dict, "weak_target", object_or_none (record->weak_target)) < 0
              || dict_set_newref (dict, "handler_id", PyLong_FromUnsignedLong (record->handler_id))
                     < 0
              || dict_set_newref (
                     dict,
                     "callable",
                     Py_XNewRef (record->callable != NULL ? record->callable : Py_None))
                     < 0
              || dict_set_newref (
                     dict,
                     "user_callable",
                     Py_XNewRef (record->user_callable != NULL ? record->user_callable : Py_None))
                     < 0)
            {
              Py_DECREF (dict);
              goto error_locked;
            }

          if (PyList_Append (list, dict) < 0)
            {
              Py_DECREF (dict);
              goto error_locked;
            }
          Py_DECREF (dict);
        }
    }
  g_mutex_unlock (&records_mutex);
  return list;

error_locked:
  g_mutex_unlock (&records_mutex);
  Py_DECREF (list);
  return NULL;
}
