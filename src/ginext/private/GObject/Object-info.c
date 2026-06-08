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

#include "GObject/Object-info.h"

#include "GObject/Fundamental.h"
#include "GObject/Object.h"
#include "marshal/enum.h"
#include "runtime/class-registry.h"

#include <weakrefobject.h>

static PyObject *gobject_wrapper_factory = NULL;
static PyObject *preallocated_gobject_wrapper_factory = NULL;
static Py_tss_t construction_depth_key = Py_tss_NEEDS_INIT;

static PyObject *
pygi_wrap_gobject_with_factory (GObject *object, GType wrapper_gtype, PyObject *factory);

static PyObject *
pygi_load_wrapper_factory (PyObject **cache, const char *attr_name)
{
  if (*cache != NULL)
    return *cache;

  PyObject *module = PyImport_ImportModule ("ginext.classbuild");
  if (module == NULL)
    return NULL;

  PyObject *factory = PyObject_GetAttrString (module, attr_name);
  Py_DECREF (module);
  if (factory == NULL)
    return NULL;
  if (!PyCallable_Check (factory))
    {
      Py_DECREF (factory);
      PyErr_Format (PyExc_TypeError, "ginext.classbuild.%s must be callable", attr_name);
      return NULL;
    }

  *cache = factory;
  return factory;
}

static PyObject *
pygi_gobject_wrapper_factory (void)
{
  return pygi_load_wrapper_factory (&gobject_wrapper_factory, "wrap_object_from_c");
}

static PyObject *
pygi_preallocated_gobject_wrapper_factory (void)
{
  return pygi_load_wrapper_factory (&preallocated_gobject_wrapper_factory,
                                    "wrap_preallocated_object_from_c");
}

static int
python_construction_depth (void)
{
  if (!PyThread_tss_is_created (&construction_depth_key)
      && PyThread_tss_create (&construction_depth_key) != 0)
    {
      PyErr_NoMemory ();
      return -1;
    }
  return (int)(uintptr_t)PyThread_tss_get (&construction_depth_key);
}

static int
set_python_construction_depth (int depth)
{
  if (!PyThread_tss_is_created (&construction_depth_key)
      && PyThread_tss_create (&construction_depth_key) != 0)
    {
      PyErr_NoMemory ();
      return -1;
    }
  if (PyThread_tss_set (&construction_depth_key, (void *)(uintptr_t)depth) != 0)
    {
      PyErr_NoMemory ();
      return -1;
    }
  return 0;
}

int
pygi_python_construction_active (void)
{
  int depth = python_construction_depth ();
  if (depth < 0)
    return -1;
  return depth > 0;
}


void
pygi_gobject_wrapper_forget_pointer (PyObject *wrapper);

static void
store_wrapper_state_if_object_survives (PyObject *wrapper);

static void
restore_wrapper_state (GObject *object, PyObject *wrapper);

static int
pygi_gobject_base_check (PyObject *wrapper)
{
  return pygi_gobject_base_type != NULL && PyObject_TypeCheck (wrapper, pygi_gobject_base_type);
}

static PyObject *
gobject_base_new_instance (PyObject *type)
{
  if (!PyType_Check (type))
    {
      PyErr_SetString (PyExc_TypeError, "expected GObjectBase subclass");
      return NULL;
    }

  PyTypeObject *wrapper_type = (PyTypeObject *)type;
  if (pygi_gobject_base_type != NULL && !PyType_IsSubtype (wrapper_type, pygi_gobject_base_type))
    {
      PyErr_SetString (PyExc_TypeError, "expected GObjectBase subclass");
      return NULL;
    }

  return wrapper_type->tp_alloc (wrapper_type, 0);
}

static GObject *
gobject_from_source (PyObject *source)
{
  GObject *object = pygi_gobject_get (source);
  if (object != NULL)
    return object;
  if (!PyErr_ExceptionMatches (PyExc_AttributeError))
    return NULL;
  PyErr_Clear ();
  if (!PyLong_Check (source))
    return NULL;
  object = (GObject *)PyLong_AsVoidPtr (source);
  if (PyErr_Occurred ())
    return NULL;
  return object;
}

static int
prime_construction_state_from_source (PyObject *self, PyObject *source, PyObject *handlers)
{
  GObject *object = gobject_from_source (source);
  if (object == NULL && PyErr_Occurred ())
    return -1;
  if (object == NULL)
    {
      PyErr_SetString (PyExc_ValueError, "GObject pointer is NULL");
      return -1;
    }

  PyObject *handler_dict
      = handlers == Py_None
            ? PyDict_New ()
            : PyObject_CallFunctionObjArgs ((PyObject *)&PyDict_Type, handlers, NULL);
  if (handler_dict == NULL)
    return -1;

  PyGIGObjectBase *base = (PyGIGObjectBase *)self;
  base->construction_ptr = object;
  Py_XSETREF (base->construction_handlers, handler_dict);
  return 0;
}

static int
apply_construction_properties_from_mapping (PyObject *self, PyObject *properties)
{
  PyGIGObjectBase *base = (PyGIGObjectBase *)self;
  if (base->construction_ptr == NULL)
    {
      PyErr_SetString (PyExc_ValueError, "no deferred construction state");
      return -1;
    }

  PyObject *mapping = PyObject_CallFunctionObjArgs ((PyObject *)&PyDict_Type, properties, NULL);
  if (mapping == NULL)
    return -1;

  Py_ssize_t pos = 0;
  PyObject *key = NULL;
  PyObject *value = NULL;
  while (PyDict_Next (mapping, &pos, &key, &value))
    {
      const char *name = PyUnicode_AsUTF8 (key);
      if (name == NULL)
        {
          Py_DECREF (mapping);
          return -1;
        }
      if (pygi_gobject_set_property_on_object (base->construction_ptr, name, value) != 0)
        {
          Py_DECREF (mapping);
          return -1;
        }
    }

  Py_DECREF (mapping);
  return 0;
}

static int
bind_wrapper_from_source (PyObject *self, PyObject *source, gboolean owns_ref)
{
  GObject *object = gobject_from_source (source);
  if (object == NULL && PyErr_Occurred ())
    return -1;
  if (object == NULL)
    {
      PyErr_SetString (PyExc_ValueError, "GObject pointer is NULL");
      return -1;
    }

  if (pygi_gobject_wrapper_store (object, self) < 0)
    return -1;

  pygi_gobject_wrapper_set_owns_ref (object, owns_ref);
  pygi_gobject_wrapper_local_set_owns_ref (self, owns_ref);
  return 0;
}

static GObject *
bound_gobject_from_self (PyObject *self, const char *method_name)
{
  GObject *object = pygi_gobject_get (self);
  if (object != NULL)
    return object;
  if (PyErr_ExceptionMatches (PyExc_AttributeError))
    {
      PyErr_Clear ();
      PyErr_Format (PyExc_ValueError, "%s() requires a bound GObject wrapper", method_name);
    }
  return NULL;
}

static PyObject *
wrap_gobject_from_source (PyObject *source)
{
  GObject *object = gobject_from_source (source);
  if (object == NULL && PyErr_Occurred ())
    return NULL;
  if (object == NULL)
    Py_RETURN_NONE;
  return pygi_gobject_to_py (object, GI_TRANSFER_NOTHING);
}

static PyObject *
wrap_preallocated_gobject_from_source (PyObject *source)
{
  GObject *object = gobject_from_source (source);
  if (object == NULL && PyErr_Occurred ())
    return NULL;
  if (object == NULL)
    Py_RETURN_NONE;
  if (!G_IS_OBJECT (object))
    return pygi_fundamental_to_py (object, GI_TRANSFER_NOTHING, pygi_gobject_wrapper_factory ());
  PyObject *factory = pygi_preallocated_gobject_wrapper_factory ();
  if (factory == NULL)
    return NULL;
  g_object_ref (object);
  PyObject *wrapper = pygi_wrap_gobject_with_factory (object, G_OBJECT_TYPE (object), factory);
  g_object_unref (object);
  return wrapper;
}

static int
GObjectBase_traverse (PyObject *self, visitproc visit, void *arg)
{
  Py_VISIT (((PyGIGObjectBase *)self)->construction_handlers);
  return PyObject_VisitManagedDict (self, visit, arg);
}

static int
GObjectBase_clear (PyObject *self)
{
  PyGIGObjectBase *base = (PyGIGObjectBase *)self;
  base->construction_ptr = NULL;
  Py_CLEAR (base->construction_handlers);
  PyObject_ClearManagedDict (self);
  return 0;
}

static PyObject *
GObjectBase_prime_construction_state (PyObject *self, PyObject *args)
{
  PyObject *source = NULL;
  PyObject *handlers = Py_None;
  if (!PyArg_ParseTuple (args, "O|O:prime_construction_state", &source, &handlers))
    return NULL;

  if (prime_construction_state_from_source (self, source, handlers) < 0)
    return NULL;
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_take_construction_state (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  PyGIGObjectBase *base = (PyGIGObjectBase *)self;
  if (base->construction_ptr == NULL)
    Py_RETURN_NONE;

  PyObject *ptr = PyLong_FromVoidPtr (base->construction_ptr);
  if (ptr == NULL)
    return NULL;

  PyObject *handlers = base->construction_handlers;
  if (handlers == NULL)
    handlers = PyDict_New ();
  else
    Py_INCREF (handlers);
  if (handlers == NULL)
    {
      Py_DECREF (ptr);
      return NULL;
    }

  base->construction_ptr = NULL;
  Py_CLEAR (base->construction_handlers);

  PyObject *state = PyTuple_Pack (2, ptr, handlers);
  Py_DECREF (ptr);
  Py_DECREF (handlers);
  return state;
}

static PyObject *
GObjectBase_construct_with_properties (PyObject *type, PyObject *args)
{
  PyObject *properties = NULL;
  if (!PyArg_ParseTuple (args, "O!:construct_with_properties", &PyDict_Type, &properties))
    return NULL;

  PyObject *call_args = PyTuple_Pack (2, type, properties);
  if (call_args == NULL)
    return NULL;
  PyObject *result = py_construct_gobject (NULL, call_args);
  Py_DECREF (call_args);
  return result;
}

static PyObject *
GObjectBase_apply_construction_properties (PyObject *self, PyObject *args)
{
  PyObject *properties = NULL;
  if (!PyArg_ParseTuple (args, "O:apply_construction_properties", &properties))
    return NULL;
  if (apply_construction_properties_from_mapping (self, properties) < 0)
    return NULL;
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_connect_constructor_handler (PyObject *self, PyObject *args)
{
  const char *signal_name = NULL;
  PyObject *callback = NULL;
  int signal_arg_limit = -1;
  if (!PyArg_ParseTuple (args,
                         "sOi:connect_constructor_handler",
                         &signal_name,
                         &callback,
                         &signal_arg_limit))
    return NULL;

  return pygi_signal_connect_full (self,
                                   signal_name,
                                   callback,
                                   FALSE,
                                   FALSE,
                                   self,
                                   Py_None,
                                   signal_arg_limit);
}

static PyObject *
GObjectBase_signal_is_action (PyObject *self, PyObject *args)
{
  const char *signal_name = NULL;
  gboolean is_action = FALSE;
  if (!PyArg_ParseTuple (args, "s:signal_is_action", &signal_name))
    return NULL;
  if (pygi_signal_is_action_full (self, signal_name, &is_action) < 0)
    return NULL;
  return PyBool_FromLong (is_action);
}

static PyObject *
GObjectBase_signal_connect (PyObject *self, PyObject *args)
{
  const char *signal_name = NULL;
  PyObject *callback = NULL;
  int after = 0;
  int once = 0;
  PyObject *owner_arg = Py_None;
  PyObject *signal_info_capsule = Py_None;
  int signal_arg_limit = -1;
  if (!PyArg_ParseTuple (args,
                         "sOpp|OOi:signal_connect",
                         &signal_name,
                         &callback,
                         &after,
                         &once,
                         &owner_arg,
                         &signal_info_capsule,
                         &signal_arg_limit))
    return NULL;

  return pygi_signal_connect_full (self,
                                   signal_name,
                                   callback,
                                   after ? TRUE : FALSE,
                                   once ? TRUE : FALSE,
                                   owner_arg,
                                   signal_info_capsule,
                                   signal_arg_limit);
}

static PyObject *
GObjectBase_signal_emit (PyObject *self, PyObject *args)
{
  const char *signal_name = NULL;
  PyObject *signal_info_capsule = Py_None;
  PyObject *emit_args = Py_None;
  if (!PyArg_ParseTuple (args, "s|OO:signal_emit", &signal_name, &signal_info_capsule, &emit_args))
    return NULL;
  return pygi_signal_emit_full (self, signal_name, signal_info_capsule, emit_args);
}

static PyObject *
GObjectBase_signal_emit_with_gtypes (PyObject *self, PyObject *args)
{
  const char *signal_name = NULL;
  PyObject *arg_gtypes_tuple = NULL;
  PyObject *emit_args = NULL;
  if (!PyArg_ParseTuple (args,
                         "sO!O!:signal_emit_with_gtypes",
                         &signal_name,
                         &PyTuple_Type,
                         &arg_gtypes_tuple,
                         &PyTuple_Type,
                         &emit_args))
    return NULL;
  return pygi_signal_emit_with_gtypes_full (self, signal_name, arg_gtypes_tuple, emit_args);
}

static PyObject *
GObjectBase_push_python_construction (PyObject *type, PyObject *Py_UNUSED (ignored))
{
  int depth = python_construction_depth ();
  if (depth < 0)
    return NULL;
  if (set_python_construction_depth (depth + 1) < 0)
    return NULL;
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_pop_python_construction (PyObject *type, PyObject *Py_UNUSED (ignored))
{
  int depth = python_construction_depth ();
  if (depth < 0)
    return NULL;
  if (set_python_construction_depth (depth <= 1 ? 0 : depth - 1) < 0)
    return NULL;
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_python_construction_active (PyObject *type, PyObject *Py_UNUSED (ignored))
{
  int active = pygi_python_construction_active ();
  if (active < 0)
    return NULL;
  return PyBool_FromLong (active);
}

static PyObject *
GObjectBase_bind_from_c (PyObject *self, PyObject *args, PyObject *kwargs)
{
  static char *keywords[] = { "source", "owns_ref", NULL };
  PyObject *source = NULL;
  int owns_ref = 1;

  if (!PyArg_ParseTupleAndKeywords (args, kwargs, "O|p:bind_from_c", keywords, &source, &owns_ref))
    return NULL;

  if (bind_wrapper_from_source (self, source, owns_ref) < 0)
    return NULL;
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_new_bound_from_c (PyObject *type, PyObject *args, PyObject *kwargs)
{
  static char *keywords[] = { "source", "owns_ref", NULL };
  PyObject *source = NULL;
  int owns_ref = 1;

  if (!PyArg_ParseTupleAndKeywords (args,
                                    kwargs,
                                    "O|p:new_bound_from_c",
                                    keywords,
                                    &source,
                                    &owns_ref))
    return NULL;

  PyObject *self = gobject_base_new_instance (type);
  if (self == NULL)
    return NULL;

  if (bind_wrapper_from_source (self, source, owns_ref) < 0)
    {
      Py_DECREF (self);
      return NULL;
    }
  return self;
}

static PyObject *
GObjectBase_new_preallocated_from_c (PyObject *type, PyObject *args, PyObject *kwargs)
{
  static char *keywords[] = { "source", "handlers", NULL };
  PyObject *source = NULL;
  PyObject *handlers = Py_None;

  if (!PyArg_ParseTupleAndKeywords (args,
                                    kwargs,
                                    "O|O:new_preallocated_from_c",
                                    keywords,
                                    &source,
                                    &handlers))
    return NULL;

  PyObject *self = gobject_base_new_instance (type);
  if (self == NULL)
    return NULL;

  if (prime_construction_state_from_source (self, source, handlers) < 0)
    {
      Py_DECREF (self);
      return NULL;
    }
  return self;
}

static PyObject *
GObjectBase_is_bound (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  return PyBool_FromLong (((PyGIGObjectBase *)self)->ptr != NULL);
}

static PyObject *
GObjectBase_owns_ref (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  gboolean owns_ref = FALSE;
  pygi_gobject_wrapper_local_owns_ref (self, &owns_ref);
  return PyBool_FromLong (owns_ref);
}

static PyObject *
GObjectBase_pointer_value (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "pointer_value");
  if (object == NULL)
    return NULL;
  return PyLong_FromVoidPtr (object);
}

static PyObject *
GObjectBase_release_ref (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "release_ref");
  if (object == NULL)
    return NULL;

  g_object_unref (object);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_preserve_wrapper_state (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  store_wrapper_state_if_object_survives (self);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_ref_sink (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "ref_sink");
  if (object == NULL)
    return NULL;

  g_object_ref_sink (object);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_make_floating (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "make_floating");
  if (object == NULL)
    return NULL;

  g_object_force_floating (object);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_ref_count (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "ref_count");
  if (object == NULL)
    return NULL;

  return PyLong_FromSize_t (object->ref_count);
}

static PyObject *
GObjectBase_is_floating (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "is_floating");
  if (object == NULL)
    return NULL;

  return PyBool_FromLong (g_object_is_floating (object));
}

static PyObject *
GObjectBase_freeze_notify (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "freeze_notify");
  if (object == NULL)
    return NULL;

  g_object_freeze_notify (object);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_thaw_notify (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "thaw_notify");
  if (object == NULL)
    return NULL;

  g_object_thaw_notify (object);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_run_dispose (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "run_dispose");
  if (object == NULL)
    return NULL;

  g_object_run_dispose (object);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_disconnect_handler_id (PyObject *self, PyObject *args)
{
  int handler_id = 0;
  if (!PyArg_ParseTuple (args, "i:disconnect_handler_id", &handler_id))
    return NULL;
  GObject *object = bound_gobject_from_self (self, "disconnect_handler_id");
  if (object == NULL)
    return NULL;

  g_signal_handler_disconnect (object, (gulong)handler_id);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_handler_id_is_connected (PyObject *self, PyObject *args)
{
  int handler_id = 0;
  if (!PyArg_ParseTuple (args, "i:handler_id_is_connected", &handler_id))
    return NULL;
  GObject *object = bound_gobject_from_self (self, "handler_id_is_connected");
  if (object == NULL)
    return NULL;

  return PyBool_FromLong (g_signal_handler_is_connected (object, (gulong)handler_id));
}

static PyObject *
GObjectBase_stop_emission_by_name (PyObject *self, PyObject *args)
{
  const char *detailed_signal = NULL;
  if (!PyArg_ParseTuple (args, "s:stop_emission_by_name", &detailed_signal))
    return NULL;
  GObject *object = bound_gobject_from_self (self, "stop_emission_by_name");
  if (object == NULL)
    return NULL;

  g_signal_stop_emission_by_name (object, detailed_signal);
  Py_RETURN_NONE;
}

static PyObject *
GObjectBase_get_property_by_name (PyObject *self, PyObject *args)
{
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "s:get_property_by_name", &name))
    return NULL;
  return pygi_gobject_get_property_by_name (self, name);
}

static PyObject *
GObjectBase_set_property_by_name (PyObject *self, PyObject *args)
{
  const char *name = NULL;
  PyObject *py_value = NULL;
  if (!PyArg_ParseTuple (args, "sO:set_property_by_name", &name, &py_value))
    return NULL;
  return pygi_gobject_set_property_by_name (self, name, py_value);
}

static PyObject *
GObjectBase_from_c (PyObject *type G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source = NULL;
  if (!PyArg_ParseTuple (args, "O:from_c", &source))
    return NULL;
  return wrap_gobject_from_source (source);
}

static PyObject *
GObjectBase_shell_from_c (PyObject *type G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source = NULL;
  if (!PyArg_ParseTuple (args, "O:shell_from_c", &source))
    return NULL;
  return wrap_preallocated_gobject_from_source (source);
}

static PyMethodDef GObjectBase_methods[] = {
  { "push_python_construction",
    GObjectBase_push_python_construction,
    METH_CLASS | METH_NOARGS,
    NULL },
  { "construct_with_properties",
    GObjectBase_construct_with_properties,
    METH_CLASS | METH_VARARGS,
    NULL },
  { "pop_python_construction",
    GObjectBase_pop_python_construction,
    METH_CLASS | METH_NOARGS,
    NULL },
  { "python_construction_active",
    GObjectBase_python_construction_active,
    METH_CLASS | METH_NOARGS,
    NULL },
  { "new_bound_from_c",
    (PyCFunction)(void (*) (void))GObjectBase_new_bound_from_c,
    METH_CLASS | METH_VARARGS | METH_KEYWORDS,
    NULL },
  { "new_preallocated_from_c",
    (PyCFunction)(void (*) (void))GObjectBase_new_preallocated_from_c,
    METH_CLASS | METH_VARARGS | METH_KEYWORDS,
    NULL },
  { "bind_from_c",
    (PyCFunction)(void (*) (void))GObjectBase_bind_from_c,
    METH_VARARGS | METH_KEYWORDS,
    NULL },
  { "is_bound", GObjectBase_is_bound, METH_NOARGS, NULL },
  { "owns_ref", GObjectBase_owns_ref, METH_NOARGS, NULL },
  { "pointer_value", GObjectBase_pointer_value, METH_NOARGS, NULL },
  { "release_ref", GObjectBase_release_ref, METH_NOARGS, NULL },
  { "preserve_wrapper_state", GObjectBase_preserve_wrapper_state, METH_NOARGS, NULL },
  { "ref_sink", GObjectBase_ref_sink, METH_NOARGS, NULL },
  { "make_floating", GObjectBase_make_floating, METH_NOARGS, NULL },
  { "ref_count", GObjectBase_ref_count, METH_NOARGS, NULL },
  { "is_floating", GObjectBase_is_floating, METH_NOARGS, NULL },
  { "freeze_notify", GObjectBase_freeze_notify, METH_NOARGS, NULL },
  { "thaw_notify", GObjectBase_thaw_notify, METH_NOARGS, NULL },
  { "run_dispose", GObjectBase_run_dispose, METH_NOARGS, NULL },
  { "disconnect_handler_id", GObjectBase_disconnect_handler_id, METH_VARARGS, NULL },
  { "handler_id_is_connected", GObjectBase_handler_id_is_connected, METH_VARARGS, NULL },
  { "stop_emission_by_name", GObjectBase_stop_emission_by_name, METH_VARARGS, NULL },
  { "get_property_by_name", GObjectBase_get_property_by_name, METH_VARARGS, NULL },
  { "set_property_by_name", GObjectBase_set_property_by_name, METH_VARARGS, NULL },
  { "from_c", GObjectBase_from_c, METH_CLASS | METH_VARARGS, NULL },
  { "shell_from_c", GObjectBase_shell_from_c, METH_CLASS | METH_VARARGS, NULL },
  { "prime_construction_state", GObjectBase_prime_construction_state, METH_VARARGS, NULL },
  { "apply_construction_properties",
    GObjectBase_apply_construction_properties,
    METH_VARARGS,
    NULL },
  { "connect_constructor_handler", GObjectBase_connect_constructor_handler, METH_VARARGS, NULL },
  { "signal_is_action", GObjectBase_signal_is_action, METH_VARARGS, NULL },
  { "signal_connect", GObjectBase_signal_connect, METH_VARARGS, NULL },
  { "signal_emit", GObjectBase_signal_emit, METH_VARARGS, NULL },
  { "signal_emit_with_gtypes", GObjectBase_signal_emit_with_gtypes, METH_VARARGS, NULL },
  { "take_construction_state", GObjectBase_take_construction_state, METH_NOARGS, NULL },
  { NULL, NULL, 0, NULL },
};

static PyGetSetDef GObjectBase_getset[] = {
  { "__dict__", PyObject_GenericGetDict, PyObject_GenericSetDict, NULL, NULL },
  { NULL },
};

static void
GObjectBase_dealloc (PyObject *self)
{
  PyObject_GC_UnTrack (self);
  PyObject_ClearWeakRefs (self);
  GObjectBase_clear (self);
  ((PyGIGObjectBase *)self)->ptr = NULL;
  ((PyGIGObjectBase *)self)->flags = 0;
  ((PyGIGObjectBase *)self)->weakreflist = NULL;
  ((PyGIGObjectBase *)self)->construction_ptr = NULL;
  ((PyGIGObjectBase *)self)->construction_handlers = NULL;
  Py_TYPE (self)->tp_free (self);
}

static PyType_Slot GinextGObjectBase_slots[] = {
  { Py_tp_new, PyType_GenericNew },
  { Py_tp_dealloc, GObjectBase_dealloc },
  { Py_tp_traverse, GObjectBase_traverse },
  { Py_tp_clear, GObjectBase_clear },
  { Py_tp_methods, GObjectBase_methods },
  { Py_tp_getset, GObjectBase_getset },
  { 0, NULL },
};

PyType_Spec GinextGObjectBase_spec = {
  .name = "ginext.private._gobject.GObjectBase",
  .basicsize = sizeof (PyGIGObjectBase),
  .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_MANAGED_DICT,
  .slots = GinextGObjectBase_slots,
};

static int
wrapper_local_bound_set (PyObject *wrapper, gboolean bound)
{
  if (!pygi_gobject_base_check (wrapper))
    return 0;
  PyGIGObjectBase *base = (PyGIGObjectBase *)wrapper;
  if (!bound)
    base->ptr = NULL;
  return 0;
}

int
pygi_gobject_wrapper_local_bound (PyObject *wrapper, gboolean *bound)
{
  if (!pygi_gobject_base_check (wrapper))
    return 0;
  *bound = ((PyGIGObjectBase *)wrapper)->ptr != NULL;
  return 1;
}

static void
wrapper_local_bound_clear (PyObject *wrapper)
{
  if (!pygi_gobject_base_check (wrapper))
    return;
  ((PyGIGObjectBase *)wrapper)->ptr = NULL;
}

static int
wrapper_local_owns_ref_set (PyObject *wrapper, gboolean owns_ref)
{
  if (!pygi_gobject_base_check (wrapper))
    return 0;
  PyGIGObjectBase *base = (PyGIGObjectBase *)wrapper;
  if (owns_ref)
    base->flags |= PYGI_GOBJECT_WRAPPER_OWNS_REF;
  else
    base->flags &= ~PYGI_GOBJECT_WRAPPER_OWNS_REF;
  return 0;
}

static int
wrapper_local_owns_ref_get (PyObject *wrapper, gboolean *owns_ref)
{
  if (!pygi_gobject_base_check (wrapper))
    return 0;
  *owns_ref = ((((PyGIGObjectBase *)wrapper)->flags & PYGI_GOBJECT_WRAPPER_OWNS_REF) != 0);
  return 1;
}

void
pygi_gobject_wrapper_local_set_owns_ref (PyObject *wrapper, gboolean owns_ref)
{
  wrapper_local_owns_ref_set (wrapper, owns_ref);
}

int
pygi_gobject_wrapper_local_owns_ref (PyObject *wrapper, gboolean *owns_ref)
{
  return wrapper_local_owns_ref_get (wrapper, owns_ref);
}

static void
wrapper_local_owns_ref_clear (PyObject *wrapper)
{
  if (!pygi_gobject_base_check (wrapper))
    return;
  ((PyGIGObjectBase *)wrapper)->flags &= ~PYGI_GOBJECT_WRAPPER_OWNS_REF;
}

static GQuark
wrapper_quark (void)
{
  static gsize quark_value = 0;
  if (g_once_init_enter (&quark_value))
    {
      GQuark quark = g_quark_from_static_string ("ginext-python-wrapper");
      g_once_init_leave (&quark_value, (gsize)quark);
    }
  return (GQuark)quark_value;
}

static GQuark
wrapper_pin_quark (void)
{
  static gsize quark_value = 0;
  if (g_once_init_enter (&quark_value))
    {
      GQuark quark = g_quark_from_static_string ("ginext-python-wrapper-pin");
      g_once_init_leave (&quark_value, (gsize)quark);
    }
  return (GQuark)quark_value;
}

static GQuark
wrapper_owns_ref_quark (void)
{
  static gsize quark_value = 0;
  if (g_once_init_enter (&quark_value))
    {
      GQuark quark = g_quark_from_static_string ("ginext-python-wrapper-owns-ref");
      g_once_init_leave (&quark_value, (gsize)quark);
    }
  return (GQuark)quark_value;
}

static GQuark
wrapper_state_quark (void)
{
  static gsize quark_value = 0;
  if (g_once_init_enter (&quark_value))
    {
      GQuark quark = g_quark_from_static_string ("ginext-python-wrapper-state");
      g_once_init_leave (&quark_value, (gsize)quark);
    }
  return (GQuark)quark_value;
}

static gpointer
wrapper_owns_ref_qdata_value (gboolean owns_ref)
{
  return GINT_TO_POINTER (owns_ref ? 2 : 1);
}

static gboolean
wrapper_owns_ref_from_qdata (gpointer value)
{
  return value != GINT_TO_POINTER (1);
}

static void
wrapper_pyobject_destroy (gpointer data)
{
  PyGILState_STATE state = PyGILState_Ensure ();
  Py_DECREF ((PyObject *)data);
  PyGILState_Release (state);
}

static void
wrapper_pointer_weak_notify (gpointer data, GObject *where_the_object_was)
{
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *weakref = (PyObject *)data;
  PyObject *wrapper = NULL;
  int status = PyWeakref_GetRef (weakref, &wrapper);
  if (status > 0 && wrapper != NULL)
    {
      if (where_the_object_was != NULL && where_the_object_was->ref_count > 0)
        {
          Py_INCREF (weakref);
          g_object_weak_ref (where_the_object_was, wrapper_pointer_weak_notify, weakref);
          Py_DECREF (wrapper);
          Py_DECREF (weakref);
          PyGILState_Release (state);
          return;
        }
      pygi_gobject_wrapper_forget_pointer (wrapper);
      Py_DECREF (wrapper);
    }
  Py_DECREF (weakref);
  PyGILState_Release (state);
}

static void
store_wrapper_state_if_object_survives (PyObject *wrapper)
{
  if (!pygi_gobject_base_check (wrapper))
    return;

  GObject *object = ((PyGIGObjectBase *)wrapper)->ptr;
  if (object == NULL || !G_IS_OBJECT (object) || object->ref_count == 0)
    return;

  PyObject **dict_ptr = _PyObject_GetDictPtr (wrapper);
  PyObject *dict = dict_ptr != NULL ? *dict_ptr : NULL;
  if (dict == NULL)
    return;
  if (!PyDict_Check (dict) || PyDict_Size (dict) == 0)
    return;

  PyObject *state = PyDict_Copy (dict);
  if (state == NULL)
    {
      PyErr_WriteUnraisable (wrapper);
      return;
    }

  g_object_set_qdata_full (object, wrapper_state_quark (), state, wrapper_pyobject_destroy);
}

static void
restore_wrapper_state (GObject *object, PyObject *wrapper)
{
  PyObject *state = g_object_steal_qdata (object, wrapper_state_quark ());
  if (state == NULL)
    return;

  if (!PyDict_Check (state))
    {
      Py_DECREF (state);
      return;
    }

  PyObject *dict = PyObject_GenericGetDict (wrapper, NULL);
  if (dict == NULL)
    {
      PyErr_WriteUnraisable (wrapper);
      Py_DECREF (state);
      return;
    }

  if (PyDict_Update (dict, state) < 0)
    PyErr_WriteUnraisable (wrapper);
  Py_DECREF (dict);
  Py_DECREF (state);
}

PyObject *
pygi_gobject_wrapper_ref (GObject *object)
{
  if (object == NULL || !G_IS_OBJECT (object))
    return NULL;

  PyObject *weakref = g_object_get_qdata (object, wrapper_quark ());
  if (weakref == NULL)
    return NULL;

  PyObject *wrapper = NULL;
  int status = PyWeakref_GetRef (weakref, &wrapper);
  if (status < 0)
    return NULL;
  if (status == 0)
    {
      g_object_set_qdata (object, wrapper_quark (), NULL);
      return NULL;
    }
  restore_wrapper_state (object, wrapper);
  return wrapper;
}

int
pygi_gobject_wrapper_store (GObject *object, PyObject *wrapper)
{
  if (object == NULL || !G_IS_OBJECT (object))
    {
      PyErr_SetString (PyExc_TypeError, "pointer is not a GObject");
      return -1;
    }

  PyObject *old_weakref = g_object_get_qdata (object, wrapper_quark ());
  if (old_weakref != NULL)
    {
      PyObject *old_wrapper = NULL;
      int status = PyWeakref_GetRef (old_weakref, &old_wrapper);
      if (status > 0 && old_wrapper != NULL)
        {
          pygi_gobject_wrapper_forget_pointer (old_wrapper);
          Py_DECREF (old_wrapper);
        }
      g_object_weak_unref (object, wrapper_pointer_weak_notify, old_weakref);
      Py_DECREF (old_weakref);
    }

  PyObject *weakref = PyWeakref_NewRef (wrapper, NULL);
  if (weakref == NULL)
    return -1;

  Py_INCREF (weakref);
  g_object_weak_ref (object, wrapper_pointer_weak_notify, weakref);
  g_object_set_qdata_full (object, wrapper_quark (), weakref, wrapper_pyobject_destroy);
  pygi_gobject_wrapper_bind_pointer (wrapper, object);
  if (wrapper_local_bound_set (wrapper, TRUE) < 0)
    PyErr_Clear ();
  if (wrapper_local_owns_ref_set (wrapper, TRUE) < 0)
    PyErr_Clear ();
  restore_wrapper_state (object, wrapper);
  return 0;
}

void
pygi_gobject_wrapper_clear (GObject *object)
{
  if (object == NULL || !G_IS_OBJECT (object))
    return;

  PyObject *weakref = g_object_get_qdata (object, wrapper_quark ());
  if (weakref != NULL)
    {
      g_object_weak_unref (object, wrapper_pointer_weak_notify, weakref);
      Py_DECREF (weakref);
    }

  PyObject *wrapper = pygi_gobject_wrapper_ref (object);
  if (wrapper != NULL)
    {
      pygi_gobject_wrapper_forget_pointer (wrapper);
      Py_DECREF (wrapper);
    }

  g_object_set_qdata (object, wrapper_quark (), NULL);
}

GObject *
pygi_gobject_wrapper_pointer (PyObject *wrapper)
{
  if (wrapper == NULL || !pygi_gobject_base_check (wrapper))
    return NULL;
  return ((PyGIGObjectBase *)wrapper)->ptr;
}

void
pygi_gobject_wrapper_bind_pointer (PyObject *wrapper, GObject *object)
{
  if (wrapper == NULL || !pygi_gobject_base_check (wrapper))
    return;
  ((PyGIGObjectBase *)wrapper)->ptr = object;
}

void
pygi_gobject_wrapper_forget_pointer (PyObject *wrapper)
{
  if (wrapper == NULL || !pygi_gobject_base_check (wrapper))
    return;
  ((PyGIGObjectBase *)wrapper)->ptr = NULL;
  wrapper_local_bound_clear (wrapper);
  wrapper_local_owns_ref_clear (wrapper);
}

gboolean
pygi_gobject_wrapper_owns_ref (GObject *object)
{
  if (object == NULL || !G_IS_OBJECT (object))
    return TRUE;
  return wrapper_owns_ref_from_qdata (g_object_get_qdata (object, wrapper_owns_ref_quark ()));
}

void
pygi_gobject_wrapper_set_owns_ref (GObject *object, gboolean owns_ref)
{
  if (object == NULL || !G_IS_OBJECT (object))
    return;
  g_object_set_qdata (object, wrapper_owns_ref_quark (), wrapper_owns_ref_qdata_value (owns_ref));
  PyObject *wrapper = pygi_gobject_wrapper_ref (object);
  if (wrapper != NULL)
    {
      if (wrapper_local_owns_ref_set (wrapper, owns_ref) < 0)
        PyErr_Clear ();
      Py_DECREF (wrapper);
    }
}

int
pygi_gobject_wrapper_pin (GObject *object, PyObject *wrapper)
{
  if (object == NULL || !G_IS_OBJECT (object))
    {
      PyErr_SetString (PyExc_TypeError, "pointer is not a GObject");
      return -1;
    }

  Py_INCREF (wrapper);
  g_object_set_qdata_full (object, wrapper_pin_quark (), wrapper, wrapper_pyobject_destroy);
  return 0;
}

void
pygi_gobject_wrapper_unpin (GObject *object)
{
  if (object == NULL || !G_IS_OBJECT (object))
    return;
  g_object_set_qdata (object, wrapper_pin_quark (), NULL);
}

static PyObject *
pygi_expected_gobject_type_name (GType gtype)
{
  if (gtype == G_TYPE_INVALID || gtype == G_TYPE_NONE)
    return PyUnicode_FromString ("GObject");

  g_autoptr (GIBaseInfo) info = gi_repository_find_by_gtype (ginext_shared_repository (), gtype);
  if (info == NULL)
    {
      PyObject *cls = pygi_class_registry_get_pytype_for_gtype (gtype);
      if (cls != NULL)
        {
          PyObject *module = PyObject_GetAttrString (cls, "__module__");
          PyObject *name = PyObject_GetAttrString (cls, "__name__");
          if (module != NULL && name != NULL)
            {
              PyObject *qualified = PyUnicode_FromFormat ("%U.%U", module, name);
              Py_DECREF (module);
              Py_DECREF (name);
              if (qualified != NULL)
                return qualified;
            }
          Py_XDECREF (module);
          Py_XDECREF (name);
          PyErr_Clear ();
        }
    }

  if (info != NULL)
    {
      const char *namespace_name = gi_base_info_get_namespace (info);
      const char *name = gi_base_info_get_name (info);
      if (namespace_name != NULL && name != NULL)
        return PyUnicode_FromFormat ("%s.%s", namespace_name, name);
    }

  const char *type_name = g_type_name (gtype);
  return PyUnicode_FromString (type_name != NULL ? type_name : "GObject");
}

static PyObject *
pygi_actual_object_display (PyObject *actual)
{
  PyObject *actual_repr = PyObject_Repr (actual);
  if (actual_repr != NULL)
    return actual_repr;

  PyErr_Clear ();

  PyObject *cls = (PyObject *)Py_TYPE (actual);
  PyObject *module = PyObject_GetAttrString (cls, "__module__");
  PyObject *name = PyObject_GetAttrString (cls, "__name__");
  if (module != NULL && name != NULL)
    {
      PyObject *fallback
          = PyUnicode_FromFormat ("<%U.%U object at %p>", module, name, (void *)actual);
      Py_DECREF (module);
      Py_DECREF (name);
      return fallback;
    }
  Py_XDECREF (module);
  Py_XDECREF (name);
  PyErr_Clear ();

  return PyUnicode_FromFormat ("<%.200s object at %p>", Py_TYPE (actual)->tp_name, (void *)actual);
}

static PyObject *
pygi_wrap_gobject_with_factory (GObject *object, GType wrapper_gtype, PyObject *factory)
{
  if (factory == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "GObject wrapper factory is not registered");
      return NULL;
    }

  Py_AUTO_DECREF PyObject *ptr = PyLong_FromVoidPtr (object);
  if (ptr == NULL)
    return NULL;

  Py_AUTO_DECREF PyObject *gtype = PyLong_FromUnsignedLongLong ((unsigned long long)wrapper_gtype);
  if (gtype == NULL)
    return NULL;

  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    return NULL;

  return PyObject_CallFunctionObjArgs (factory, ptr, gtype, context, NULL);
}

PyObject *
pygi_gtype_value_to_py (GType gtype)
{
  return PyLong_FromUnsignedLongLong ((unsigned long long)gtype);
}

static gpointer
pygi_fundamental_wrapper_pointer (PyObject *wrapper)
{
  PyObject **dict_ptr = _PyObject_GetDictPtr (wrapper);
  if (dict_ptr == NULL || *dict_ptr == NULL)
    return NULL;

  PyObject *ptr = PyDict_GetItemString (*dict_ptr, "_pointer");
  if (ptr == NULL)
    return NULL;

  gpointer instance = (gpointer)PyLong_AsVoidPtr (ptr);
  if (PyErr_Occurred ())
    return NULL;
  return instance;
}

GObject *
pygi_gobject_get (PyObject *wrapper)
{
  GObject *object = pygi_gobject_wrapper_pointer (wrapper);
  if (object != NULL)
    return object;
  if (PyErr_Occurred ())
    return NULL;

  object = (GObject *)pygi_fundamental_wrapper_pointer (wrapper);
  if (object != NULL)
    return object;
  if (PyErr_Occurred ())
    return NULL;

  PyErr_SetString (PyExc_AttributeError, "wrapper is not bound");
  return NULL;
}

int
pygi_raise_gobject_type_error (const char *expected, PyObject *actual)
{
  PyObject *actual_repr = pygi_actual_object_display (actual);
  if (actual_repr == NULL)
    return -1;

  PyErr_Format (PyExc_TypeError,
                "expected a %s, but got %U",
                expected != NULL ? expected : "GObject",
                actual_repr);
  Py_DECREF (actual_repr);
  return -1;
}

int
pygi_raise_gobject_type_error_for_gtype (GType expected_gtype, PyObject *actual)
{
  PyObject *expected = pygi_expected_gobject_type_name (expected_gtype);
  if (expected == NULL)
    return -1;

  PyObject *actual_repr = pygi_actual_object_display (actual);
  if (actual_repr == NULL)
    {
      Py_DECREF (expected);
      return -1;
    }

  PyErr_Format (PyExc_TypeError, "expected a %U, but got %U", expected, actual_repr);
  Py_DECREF (expected);
  Py_DECREF (actual_repr);
  return -1;
}

int
pygi_object_info_from_py (PyObject *value, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  if (value == Py_None)
    {
      out->v_pointer = NULL;
      return 0;
    }
  GObject *object = pygi_gobject_get (value);
  if (object == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return pygi_raise_gobject_type_error_for_gtype (G_TYPE_OBJECT, value);
        }
      return -1;
    }
  out->v_pointer = object;
  return 0;
}

PyObject *
pygi_gobject_to_py_as_gtype (GObject *object, GType wrapper_gtype, GITransfer transfer)
{
  if (object == NULL)
    return Py_NewRef (Py_None);

  if (!G_IS_OBJECT (object))
    return pygi_fundamental_to_py (object, transfer, pygi_gobject_wrapper_factory ());

  PyObject *cached_wrapper = pygi_gobject_wrapper_ref (object);
  if (cached_wrapper != NULL)
    {
      gboolean owns_ref = pygi_gobject_wrapper_owns_ref (object);
      if (transfer == GI_TRANSFER_NOTHING && !owns_ref)
        g_object_ref (object);
      if (transfer != GI_TRANSFER_NOTHING || !owns_ref)
        pygi_gobject_wrapper_set_owns_ref (object, TRUE);
      if (!owns_ref || transfer != GI_TRANSFER_NOTHING)
        pygi_gobject_wrapper_unpin (object);
      return cached_wrapper;
    }
  if (PyErr_Occurred ())
    {
      return NULL;
    }

  if (transfer == GI_TRANSFER_NOTHING)
    g_object_ref (object);

  PyObject *factory = pygi_gobject_wrapper_factory ();
  if (factory == NULL)
    goto error;

  PyObject *ptr = PyLong_FromVoidPtr (object);
  if (ptr == NULL)
    goto error;

  GType actual_gtype = G_OBJECT_TYPE (object);
  if (wrapper_gtype != actual_gtype)
    {
      PyObject *actual = PyLong_FromUnsignedLongLong ((unsigned long long)actual_gtype);
      if (actual == NULL)
        {
          Py_DECREF (ptr);
          goto error;
        }
      PyObject *context = pygi_namespace_context ();
      if (context == NULL)
        {
          Py_DECREF (actual);
          Py_DECREF (ptr);
          goto error;
        }
      PyObject *actual_wrapper = PyObject_CallFunctionObjArgs (factory, ptr, actual, context, NULL);
      Py_DECREF (actual);
      if (actual_wrapper != NULL)
        {
          Py_DECREF (ptr);
          return actual_wrapper;
        }
      PyErr_Clear ();
    }

  PyObject *gtype = PyLong_FromUnsignedLongLong ((unsigned long long)wrapper_gtype);
  if (gtype == NULL)
    {
      Py_DECREF (ptr);
      goto error;
    }

  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    {
      Py_DECREF (ptr);
      Py_DECREF (gtype);
      goto error;
    }
  PyObject *wrapper = PyObject_CallFunctionObjArgs (factory, ptr, gtype, context, NULL);
  Py_DECREF (ptr);
  Py_DECREF (gtype);
  if (wrapper == NULL)
    goto error;
  return wrapper;

error:
  g_object_unref (object);
  return NULL;
}

PyObject *
pygi_gobject_to_py (GObject *object, GITransfer transfer)
{
  return pygi_gobject_to_py_as_gtype (object,
                                      object != NULL ? G_OBJECT_TYPE (object) : G_TYPE_INVALID,
                                      transfer);
}

PyObject *
pygi_wrap_preallocated_gobject (GObject *object, GType wrapper_gtype)
{
  if (object == NULL)
    return Py_NewRef (Py_None);
  if (!G_IS_OBJECT (object))
    return pygi_fundamental_to_py (object, GI_TRANSFER_NOTHING, pygi_gobject_wrapper_factory ());
  PyObject *factory = pygi_preallocated_gobject_wrapper_factory ();
  if (factory == NULL)
    return NULL;
  return pygi_wrap_gobject_with_factory (object, wrapper_gtype, factory);
}

PyObject *
pygi_object_info_to_py (GIArgument *arg, GITransfer transfer)
{
  g_return_val_if_fail (arg != NULL, NULL);
  return pygi_gobject_to_py (arg->v_pointer, transfer);
}

PyObject *
py_wrap_gobject_pointer (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source = NULL;
  if (!PyArg_ParseTuple (args, "O", &source))
    return NULL;
  return wrap_gobject_from_source (source);
}

PyObject *
py_wrap_preallocated_gobject_pointer (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source = NULL;
  if (!PyArg_ParseTuple (args, "O", &source))
    return NULL;
  return wrap_preallocated_gobject_from_source (source);
}
