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

/* Private Python entry points to exercise the signal closure layer
 * without the abi2 attribute machinery. Tests call into these via
 * ginext.private.signal_connect / signal_emit. */
#include "common.h"
#include "GObject/Closure.h"
#include "GObject/Closure-record.h"
#include "GObject/Object-info.h"
#include "GIRepository/BaseInfo.h"
#include "marshal/gvalue.h"

#include <girepository/girepository.h>
#include <string.h>

#define info_from_capsule gi_info_from_py_or_none

static GObject *
gobject_from_source_arg (PyObject *arg)
{
  GObject *source = pygi_gobject_get (arg);
  if (source != NULL)
    return source;
  if (!PyErr_ExceptionMatches (PyExc_AttributeError))
    return NULL;
  PyErr_Clear ();
  if (!PyLong_Check (arg))
    return NULL;
  source = (GObject *)PyLong_AsVoidPtr (arg);
  if (PyErr_Occurred ())
    return NULL;
  return source;
}

/* Map a GITypeInfo onto the GType to use for a GValue holding a signal
 * argument. Covers the primitive tags and any registered interface type
 * (objects, enums, flags, boxed). Returns 0 on success, -1 with a
 * Python error set on failure. */
static int
arg_type_info_to_gtype (GITypeInfo *ti, GType *out)
{
  GITypeTag tag = gi_type_info_get_tag (ti);
  switch (tag)
    {
    case GI_TYPE_TAG_BOOLEAN:
      *out = G_TYPE_BOOLEAN;
      return 0;
    case GI_TYPE_TAG_INT8:
      *out = G_TYPE_CHAR;
      return 0;
    case GI_TYPE_TAG_UINT8:
      *out = G_TYPE_UCHAR;
      return 0;
    case GI_TYPE_TAG_INT16:
    case GI_TYPE_TAG_INT32:
      *out = G_TYPE_INT;
      return 0;
    case GI_TYPE_TAG_UINT16:
    case GI_TYPE_TAG_UINT32:
      *out = G_TYPE_UINT;
      return 0;
    case GI_TYPE_TAG_INT64:
      *out = G_TYPE_INT64;
      return 0;
    case GI_TYPE_TAG_UINT64:
      *out = G_TYPE_UINT64;
      return 0;
    case GI_TYPE_TAG_FLOAT:
      *out = G_TYPE_FLOAT;
      return 0;
    case GI_TYPE_TAG_DOUBLE:
      *out = G_TYPE_DOUBLE;
      return 0;
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      *out = G_TYPE_STRING;
      return 0;
    case GI_TYPE_TAG_INTERFACE:
      {
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
        if (iface == NULL)
          {
            PyErr_SetString (PyExc_TypeError, "signal arg has unresolved interface type");
            return -1;
          }
        *out = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
        if (*out == 0)
          {
            PyErr_SetString (PyExc_TypeError, "signal arg interface has no GType");
            return -1;
          }
        return 0;
      }
    default:
      PyErr_Format (PyExc_NotImplementedError,
                    "signal emit: arg type tag %d not supported yet",
                    tag);
      return -1;
    }
}

static PyObject *
emit_values_and_return (GValue *gvalues, guint signal_id, GQuark detail)
{
  GSignalQuery query;
  g_signal_query (signal_id, &query);
  if (query.signal_id == 0)
    {
      PyErr_SetString (PyExc_ValueError, "invalid signal id");
      return NULL;
    }

  GType return_type = query.return_type & ~G_SIGNAL_TYPE_STATIC_SCOPE;
  GValue return_value = G_VALUE_INIT;
  GValue *return_ptr = NULL;
  if (return_type != G_TYPE_NONE)
    {
      g_value_init (&return_value, return_type);
      return_ptr = &return_value;
    }

  g_signal_emitv (gvalues, signal_id, detail, return_ptr);

  if (return_ptr == NULL)
    Py_RETURN_NONE;

  PyObject *py_result = pygi_gvalue_value_to_py (&return_value);
  g_value_unset (&return_value);
  return py_result;
}

static gboolean
py_signal_emission_hook (GSignalInvocationHint *hint,
                         guint n_param_values,
                         const GValue *param_values,
                         gpointer data)
{
  (void)hint;
  PyObject *callback = data;
  PyGILState_STATE state = PyGILState_Ensure ();

  PyObject *instance = NULL;
  if (n_param_values > 0)
    instance = pygi_gvalue_value_to_py ((GValue *)&param_values[0]);
  if (instance == NULL)
    {
      PyErr_Clear ();
      Py_INCREF (Py_None);
      instance = Py_None;
    }

  PyObject *result = PyObject_CallFunctionObjArgs (callback, instance, NULL);
  Py_DECREF (instance);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return FALSE;
    }

  gboolean keep = FALSE;
  if (result != Py_None)
    {
      int truthy = PyObject_IsTrue (result);
      if (truthy < 0)
        {
          PyErr_Print ();
          keep = FALSE;
        }
      else
        keep = truthy ? TRUE : FALSE;
    }
  Py_DECREF (result);
  PyGILState_Release (state);
  return keep;
}

typedef struct
{
  PyObject *callback;
  PyObject *user_data;
} PySignalAccumulatorData;

static gboolean
py_signal_accumulator (GSignalInvocationHint *ihint,
                       GValue *return_accu,
                       const GValue *handler_return,
                       gpointer data)
{
  (void)ihint;
  PySignalAccumulatorData *accu_data = data;
  PyGILState_STATE state = PyGILState_Ensure ();

  PyObject *return_accu_obj = pygi_gvalue_value_to_py (return_accu);
  if (return_accu_obj == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return FALSE;
    }
  PyObject *handler_return_obj = pygi_gvalue_value_to_py ((GValue *)handler_return);
  if (handler_return_obj == NULL)
    {
      Py_DECREF (return_accu_obj);
      PyErr_Print ();
      PyGILState_Release (state);
      return FALSE;
    }

  PyObject *result = PyObject_CallFunctionObjArgs (accu_data->callback,
                                                   Py_None,
                                                   return_accu_obj,
                                                   handler_return_obj,
                                                   accu_data->user_data,
                                                   NULL);
  Py_DECREF (return_accu_obj);
  Py_DECREF (handler_return_obj);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return FALSE;
    }

  PyObject *continue_obj = NULL;
  PyObject *accumulated_obj = NULL;
  if (!PyArg_ParseTuple (result, "OO", &continue_obj, &accumulated_obj))
    {
      PyErr_SetString (PyExc_TypeError, "signal accumulator must return (bool, value)");
      PyErr_Print ();
      Py_DECREF (result);
      PyGILState_Release (state);
      return FALSE;
    }

  GValue converted = G_VALUE_INIT;
  gboolean keep_emitting = FALSE;
  if (pygi_py_to_gvalue_targeted (G_VALUE_TYPE (return_accu),
                                  accumulated_obj,
                                  &converted,
                                  "signal accumulator")
      != 0)
    {
      PyErr_Print ();
      Py_DECREF (result);
      PyGILState_Release (state);
      return FALSE;
    }
  g_value_copy (&converted, return_accu);
  g_value_unset (&converted);

  int truthy = PyObject_IsTrue (continue_obj);
  if (truthy < 0)
    PyErr_Print ();
  else
    keep_emitting = truthy ? TRUE : FALSE;

  Py_DECREF (result);
  PyGILState_Release (state);
  return keep_emitting;
}

static void
py_signal_accumulator_data_destroy (gpointer data)
{
  PySignalAccumulatorData *accu_data = data;
  PyGILState_STATE state = PyGILState_Ensure ();
  Py_DECREF (accu_data->callback);
  Py_DECREF (accu_data->user_data);
  PyGILState_Release (state);
  g_free (accu_data);
}

static int
resolve_signal_accumulator (PyObject *accumulator,
                            PyObject *accu_data,
                            GSignalAccumulator *out_accumulator,
                            gpointer *out_accu_data)
{
  *out_accumulator = NULL;
  *out_accu_data = NULL;
  if (accumulator == NULL || accumulator == Py_None)
    return 0;

  PyObject *name_obj = PyObject_GetAttrString (accumulator, "__name__");
  const char *name = name_obj != NULL ? PyUnicode_AsUTF8 (name_obj) : NULL;
  if (name != NULL && strcmp (name, "signal_accumulator_true_handled") == 0)
    {
      *out_accumulator = g_signal_accumulator_true_handled;
      Py_DECREF (name_obj);
      return 0;
    }
  if (name != NULL && strcmp (name, "signal_accumulator_first_wins") == 0)
    {
      *out_accumulator = g_signal_accumulator_first_wins;
      Py_DECREF (name_obj);
      return 0;
    }
  Py_XDECREF (name_obj);
  PyErr_Clear ();

  if (!PyCallable_Check (accumulator))
    {
      PyErr_SetString (PyExc_TypeError, "signal accumulator must be callable");
      return -1;
    }

  PySignalAccumulatorData *data = g_new0 (PySignalAccumulatorData, 1);
  Py_INCREF (accumulator);
  Py_INCREF (accu_data);
  data->callback = accumulator;
  data->user_data = accu_data;
  *out_accumulator = py_signal_accumulator;
  *out_accu_data = data;
  return 0;
}

static void
py_signal_emission_hook_destroy (gpointer data)
{
  PyGILState_STATE state = PyGILState_Ensure ();
  Py_DECREF ((PyObject *)data);
  PyGILState_Release (state);
}

PyObject *
pygi_signal_add_emission_hook_full (GType gtype, const char *signal_name, PyObject *callback)
{
  if (!PyCallable_Check (callback))
    {
      PyErr_SetString (PyExc_TypeError, "callback must be callable");
      return NULL;
    }

  guint signal_id = 0;
  GQuark detail = 0;
  if (!g_signal_parse_name (signal_name, gtype, &signal_id, &detail, TRUE))
    {
      PyErr_Format (PyExc_ValueError, "no such signal: %s on %s", signal_name, g_type_name (gtype));
      return NULL;
    }

  Py_INCREF (callback);
  gulong hook_id = g_signal_add_emission_hook (signal_id,
                                               detail,
                                               py_signal_emission_hook,
                                               callback,
                                               py_signal_emission_hook_destroy);
  if (hook_id == 0)
    {
      Py_DECREF (callback);
      PyErr_Format (PyExc_RuntimeError, "failed to add emission hook for %s", signal_name);
      return NULL;
    }
  return PyLong_FromUnsignedLong (hook_id);
}

PyObject *
py_signal_add_emission_hook (PyObject *m, PyObject *args)
{
  (void)m;
  unsigned long long gtype_arg;
  const char *signal_name;
  PyObject *callback;
  if (!PyArg_ParseTuple (args, "KsO", &gtype_arg, &signal_name, &callback))
    return NULL;
  return pygi_signal_add_emission_hook_full ((GType)gtype_arg, signal_name, callback);
}

PyObject *
pygi_signal_remove_emission_hook_full (GType gtype, const char *signal_name, gulong hook_id)
{
  guint signal_id = 0;
  GQuark detail = 0;
  if (!g_signal_parse_name (signal_name, gtype, &signal_id, &detail, TRUE))
    {
      PyErr_Format (PyExc_ValueError, "no such signal: %s on %s", signal_name, g_type_name (gtype));
      return NULL;
    }
  g_signal_remove_emission_hook (signal_id, hook_id);
  Py_RETURN_NONE;
}

PyObject *
py_signal_remove_emission_hook (PyObject *m, PyObject *args)
{
  (void)m;
  unsigned long long gtype_arg;
  const char *signal_name;
  unsigned long hook_id;
  if (!PyArg_ParseTuple (args, "Ksk", &gtype_arg, &signal_name, &hook_id))
    return NULL;
  return pygi_signal_remove_emission_hook_full ((GType)gtype_arg, signal_name, (gulong)hook_id);
}

PyObject *
pygi_signal_connect_full (PyObject *source_arg,
                          const char *signal_name,
                          PyObject *callback,
                          gboolean after,
                          gboolean once,
                          PyObject *owner_arg,
                          PyObject *signal_info_capsule,
                          int signal_arg_limit)
{
  if (!PyCallable_Check (callback))
    {
      PyErr_SetString (PyExc_TypeError, "callback must be callable");
      return NULL;
    }

  GObject *source = gobject_from_source_arg (source_arg);
  if (source == NULL && PyErr_Occurred ())
    return NULL;
  if (source == NULL || !G_IS_OBJECT (source))
    {
      PyErr_SetString (PyExc_TypeError, "source is not a GObject");
      return NULL;
    }
  GObject *owner = NULL;
  if (owner_arg != Py_None)
    {
      owner = gobject_from_source_arg (owner_arg);
      if (owner == NULL && PyErr_Occurred ())
        return NULL;
      if (!G_IS_OBJECT (owner))
        {
          PyErr_SetString (PyExc_TypeError, "owner is not a GObject");
          return NULL;
        }
    }

  guint signal_id = 0;
  GQuark detail = 0;
  if (!g_signal_parse_name (signal_name, G_OBJECT_TYPE (source), &signal_id, &detail, TRUE))
    {
      PyErr_Format (PyExc_ValueError,
                    "no such signal: %s on %s",
                    signal_name,
                    G_OBJECT_TYPE_NAME (source));
      return NULL;
    }

  GIBaseInfo *signal_info = info_from_capsule (signal_info_capsule);
  if (signal_info_capsule != Py_None && signal_info == NULL)
    return NULL;

  GClosure *closure = pygi_closure_new_for_signal (
      callback,
      GI_IS_CALLABLE_INFO (signal_info) ? (GICallableInfo *)signal_info : NULL);
  if (closure == NULL)
    return NULL;

  pygi_closure_set_once (closure, once);
  pygi_closure_set_signal_arg_limit (closure, signal_arg_limit);

  gulong handler_id = g_signal_connect_closure_by_id (source, signal_id, detail, closure, after);
  if (handler_id == 0)
    {
      PyErr_Format (PyExc_RuntimeError,
                    "g_signal_connect_closure_by_id failed for %s",
                    signal_name);
      return NULL;
    }

  pygi_closure_set_signal_metadata (closure, source, handler_id, NULL);
  if (owner != NULL)
    {
      PyGIClosureRecord *record = pygi_closure_get_record (closure);
      pygi_closure_record_set_owner (record, owner);
    }
  return PyLong_FromUnsignedLong (handler_id);
}

PyObject *
py_signal_connect (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *source_arg;
  const char *signal_name;
  PyObject *callback;
  int after = 0;
  int once = 0;
  PyObject *owner_arg = Py_None;
  PyObject *signal_info_capsule = Py_None;
  int signal_arg_limit = -1;
  if (!PyArg_ParseTuple (args,
                         "OsO|ppOOi",
                         &source_arg,
                         &signal_name,
                         &callback,
                         &after,
                         &once,
                         &owner_arg,
                         &signal_info_capsule,
                         &signal_arg_limit))
    return NULL;

  return pygi_signal_connect_full (source_arg,
                                   signal_name,
                                   callback,
                                   after ? TRUE : FALSE,
                                   once ? TRUE : FALSE,
                                   owner_arg,
                                   signal_info_capsule,
                                   signal_arg_limit);
}

/* Return True if the named signal carries G_SIGNAL_ACTION, i.e. it may be
 * emitted by calling it (e.g. gtk_button_clicked emits "clicked"). Used by
 * Signal.__call__ to decide whether a bare `obj.signal()` should emit. */
int
pygi_signal_is_action_full (PyObject *source_arg, const char *signal_name, gboolean *out_is_action)
{
  GObject *source = gobject_from_source_arg (source_arg);
  if (source == NULL && PyErr_Occurred ())
    return -1;
  if (source == NULL || !G_IS_OBJECT (source))
    {
      PyErr_SetString (PyExc_TypeError, "source is not a GObject");
      return -1;
    }

  guint signal_id = 0;
  GQuark detail = 0;
  if (!g_signal_parse_name (signal_name, G_OBJECT_TYPE (source), &signal_id, &detail, FALSE))
    {
      *out_is_action = FALSE;
      return 0;
    }

  GSignalQuery query;
  g_signal_query (signal_id, &query);
  if (query.signal_id == 0)
    {
      *out_is_action = FALSE;
      return 0;
    }

  *out_is_action = (query.signal_flags & G_SIGNAL_ACTION) != 0;
  return 0;
}

PyObject *
py_signal_is_action (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *source_arg;
  const char *signal_name;
  gboolean is_action = FALSE;
  if (!PyArg_ParseTuple (args, "Os", &source_arg, &signal_name))
    return NULL;
  if (pygi_signal_is_action_full (source_arg, signal_name, &is_action) < 0)
    return NULL;
  return PyBool_FromLong (is_action);
}

PyObject *
pygi_signal_emit_full (PyObject *source_arg,
                       const char *signal_name,
                       PyObject *signal_info_capsule,
                       PyObject *emit_args)
{
  if (signal_info_capsule == NULL)
    signal_info_capsule = Py_None;
  if (emit_args == NULL)
    emit_args = Py_None;

  GObject *source = gobject_from_source_arg (source_arg);
  if (source == NULL && PyErr_Occurred ())
    return NULL;
  if (source == NULL || !G_IS_OBJECT (source))
    {
      PyErr_SetString (PyExc_TypeError, "source is not a GObject");
      return NULL;
    }

  guint signal_id = 0;
  GQuark detail = 0;
  if (!g_signal_parse_name (signal_name, G_OBJECT_TYPE (source), &signal_id, &detail, FALSE))
    {
      PyErr_Format (PyExc_ValueError,
                    "no such signal: %s on %s",
                    signal_name,
                    G_OBJECT_TYPE_NAME (source));
      return NULL;
    }

  Py_ssize_t n_emit = 0;
  if (emit_args != Py_None)
    {
      if (!PyTuple_Check (emit_args))
        {
          PyErr_SetString (PyExc_TypeError, "emit args must be a tuple");
          return NULL;
        }
      n_emit = PyTuple_GET_SIZE (emit_args);
    }

  if (n_emit == 0)
    {
      GValue instance = G_VALUE_INIT;
      g_value_init (&instance, G_OBJECT_TYPE (source));
      g_value_set_object (&instance, source);
      PyObject *result = emit_values_and_return (&instance, signal_id, detail);
      g_value_unset (&instance);
      return result;
    }

  GIBaseInfo *base = info_from_capsule (signal_info_capsule);
  if (base == NULL)
    {
      PyErr_SetString (PyExc_TypeError, "signal_info capsule required for emit with args");
      return NULL;
    }
  GICallableInfo *sig_info = (GICallableInfo *)base;
  guint n_sig_args = gi_callable_info_get_n_args (sig_info);
  if ((guint)n_emit != n_sig_args)
    {
      PyErr_Format (PyExc_TypeError,
                    "signal %s expects %u argument(s), got %zd",
                    signal_name,
                    n_sig_args,
                    n_emit);
      return NULL;
    }

  GValue *gvalues = g_new0 (GValue, 1 + n_emit);
  g_value_init (&gvalues[0], G_OBJECT_TYPE (source));
  g_value_set_object (&gvalues[0], source);

  int failed = 0;
  for (guint i = 0; i < n_sig_args && !failed; i++)
    {
      g_autoptr (GIArgInfo) arg_info = gi_callable_info_get_arg (sig_info, (gint)i);
      g_autoptr (GITypeInfo) ti = gi_arg_info_get_type_info (arg_info);
      GType gtype = 0;
      if (arg_type_info_to_gtype (ti, &gtype) < 0)
        {
          failed = 1;
          break;
        }
      PyObject *py_arg = PyTuple_GET_ITEM (emit_args, (Py_ssize_t)i);
      if (pygi_py_to_gvalue_targeted (gtype, py_arg, &gvalues[1 + i], "signal emit arg") < 0)
        failed = 1;
    }

  PyObject *result = NULL;
  if (!failed)
    result = emit_values_and_return (gvalues, signal_id, detail);

  for (Py_ssize_t i = 0; i < 1 + n_emit; i++)
    {
      if (G_IS_VALUE (&gvalues[i]))
        g_value_unset (&gvalues[i]);
    }
  g_free (gvalues);

  if (failed)
    return NULL;
  return result;
}

PyObject *
py_signal_emit (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *source_arg;
  const char *signal_name;
  PyObject *signal_info_capsule = Py_None;
  PyObject *emit_args = Py_None;
  if (!PyArg_ParseTuple (args,
                         "Os|OO",
                         &source_arg,
                         &signal_name,
                         &signal_info_capsule,
                         &emit_args))
    return NULL;
  return pygi_signal_emit_full (source_arg, signal_name, signal_info_capsule, emit_args);
}

int
pygi_register_signal_for_gtype (GType gtype,
                                const char *signal_name,
                                GType return_gtype,
                                PyObject *arg_gtypes_tuple,
                                GSignalFlags signal_flags,
                                PyObject *accumulator_obj,
                                PyObject *accu_data_obj,
                                guint *out_signal_id)
{
  /* return_gtype_arg == 0 is the convenient Python sentinel for "void
   * return" — translate to the real G_TYPE_NONE which is a non-zero
   * runtime fundamental on most platforms. */
  if (return_gtype == 0)
    return_gtype = G_TYPE_NONE;
  Py_ssize_t n_args = PyTuple_GET_SIZE (arg_gtypes_tuple);

  GType *params = NULL;
  if (n_args > 0)
    {
      params = g_new0 (GType, n_args);
      for (Py_ssize_t i = 0; i < n_args; i++)
        {
          PyObject *item = PyTuple_GET_ITEM (arg_gtypes_tuple, i);
          unsigned long long gt = PyLong_AsUnsignedLongLong (item);
          if (gt == (unsigned long long)-1 && PyErr_Occurred ())
            {
              g_free (params);
              return -1;
            }
          params[i] = (GType)gt;
        }
    }

  /* g_signal_newv requires the GType to have its class structure
   * instantiated. The class isn't created until the first instance is
   * allocated, so force it now with g_type_class_ref. We don't unref
   * because the class is intended to live for the type's lifetime. */
  g_type_class_ref (gtype);
  GSignalAccumulator accumulator = NULL;
  gpointer acc_data = NULL;
  if (resolve_signal_accumulator (accumulator_obj, accu_data_obj, &accumulator, &acc_data) != 0)
    {
      g_free (params);
      return -1;
    }
  guint signal_id = g_signal_newv (signal_name,
                                   gtype,
                                   signal_flags,
                                   NULL, /* class_closure */
                                   accumulator,
                                   acc_data,
                                   NULL, /* c_marshaller (NULL = use generic) */
                                   return_gtype,
                                   (guint)n_args,
                                   params);
  g_free (params);
  if (signal_id == 0)
    {
      if (acc_data != NULL && accumulator == py_signal_accumulator)
        py_signal_accumulator_data_destroy (acc_data);
      PyErr_Format (PyExc_RuntimeError,
                    "g_signal_newv failed for %s on %s",
                    signal_name,
                    g_type_name (gtype));
      return -1;
    }
  *out_signal_id = signal_id;
  return 0;
}

PyObject *
pygi_signal_emit_with_gtypes_full (PyObject *source_arg,
                                   const char *signal_name,
                                   PyObject *arg_gtypes_tuple,
                                   PyObject *emit_args)
{
  GObject *source = gobject_from_source_arg (source_arg);
  if (source == NULL && PyErr_Occurred ())
    return NULL;
  if (source == NULL || !G_IS_OBJECT (source))
    {
      PyErr_SetString (PyExc_TypeError, "source is not a GObject");
      return NULL;
    }

  guint signal_id = 0;
  GQuark detail = 0;
  if (!g_signal_parse_name (signal_name, G_OBJECT_TYPE (source), &signal_id, &detail, FALSE))
    {
      PyErr_Format (PyExc_ValueError,
                    "no such signal: %s on %s",
                    signal_name,
                    G_OBJECT_TYPE_NAME (source));
      return NULL;
    }

  Py_ssize_t n_emit = PyTuple_GET_SIZE (emit_args);
  Py_ssize_t n_decl = PyTuple_GET_SIZE (arg_gtypes_tuple);
  if (n_emit != n_decl)
    {
      PyErr_Format (PyExc_TypeError,
                    "signal %s expects %zd argument(s), got %zd",
                    signal_name,
                    n_decl,
                    n_emit);
      return NULL;
    }

  GValue *gvalues = g_new0 (GValue, 1 + n_emit);
  g_value_init (&gvalues[0], G_OBJECT_TYPE (source));
  g_value_set_object (&gvalues[0], source);

  int failed = 0;
  for (Py_ssize_t i = 0; i < n_emit && !failed; i++)
    {
      PyObject *gt_obj = PyTuple_GET_ITEM (arg_gtypes_tuple, i);
      unsigned long long gt = PyLong_AsUnsignedLongLong (gt_obj);
      if (gt == (unsigned long long)-1 && PyErr_Occurred ())
        {
          failed = 1;
          break;
        }
      PyObject *py_arg = PyTuple_GET_ITEM (emit_args, i);
      if (pygi_py_to_gvalue_targeted ((GType)gt, py_arg, &gvalues[1 + i], "signal emit arg") < 0)
        failed = 1;
    }

  PyObject *result = NULL;
  if (!failed)
    result = emit_values_and_return (gvalues, signal_id, detail);

  for (Py_ssize_t i = 0; i < 1 + n_emit; i++)
    {
      if (G_IS_VALUE (&gvalues[i]))
        g_value_unset (&gvalues[i]);
    }
  g_free (gvalues);

  if (failed)
    return NULL;
  return result;
}

PyObject *
py_signal_emit_with_gtypes (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *source_arg;
  const char *signal_name;
  PyObject *arg_gtypes_tuple;
  PyObject *emit_args;
  if (!PyArg_ParseTuple (args,
                         "OsO!O!",
                         &source_arg,
                         &signal_name,
                         &PyTuple_Type,
                         &arg_gtypes_tuple,
                         &PyTuple_Type,
                         &emit_args))
    return NULL;
  return pygi_signal_emit_with_gtypes_full (source_arg, signal_name, arg_gtypes_tuple, emit_args);
}
