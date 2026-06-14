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
#include "GObject/ObjectMeta.h"
#include "GObject/GIMeta.h"
#include "marshal/conversion.h"
#include "marshal/enum.h"
#include "runtime/class-registry.h"

#include <weakrefobject.h>

static Py_tss_t construction_depth_key = Py_tss_NEEDS_INIT;

/* GType -> PyTypeObject* registry. Populated by classbuild as each ginext class
 * is built; lets pygi_gobject_to_py_as_gtype find the wrapper class without a
 * Python factory dispatch on the hot path. Values are borrowed (the class is kept
 * alive by classbuild's own _classes_by_gtype dict). */
static GHashTable *pygi_gtype_to_pytype = NULL;

void
pygi_register_gtype_pytype (GType gtype, PyTypeObject *type)
{
  if (gtype == 0)
    return;
  if (pygi_gtype_to_pytype == NULL)
    pygi_gtype_to_pytype = g_hash_table_new (g_direct_hash, g_direct_equal);
  g_hash_table_replace (pygi_gtype_to_pytype,
                        (gpointer)(guintptr)gtype,
                        (gpointer)type);
}

PyTypeObject *
pygi_lookup_gtype_pytype (GType gtype)
{
  if (pygi_gtype_to_pytype == NULL || gtype == 0)
    return NULL;
  return (PyTypeObject *)g_hash_table_lookup (pygi_gtype_to_pytype,
                                              (gpointer)(guintptr)gtype);
}

PyObject *
py_register_gtype_pytype (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  unsigned long long gtype_arg = 0;
  PyObject *type = NULL;
  if (!PyArg_ParseTuple (args, "KO", &gtype_arg, &type))
    return NULL;
  if (!PyType_Check (type))
    {
      PyErr_SetString (PyExc_TypeError, "register_gtype_pytype: expected a type");
      return NULL;
    }
  pygi_register_gtype_pytype ((GType)gtype_arg, (PyTypeObject *)type);
  Py_RETURN_NONE;
}


static PyObject *
pygi_wrap_gobject_with_factory (GObject *object, GType wrapper_gtype, PyObject *factory);

/* Defined alongside tp_init below; new_bound_from_c runs post-construct hooks. */
static int
gobject_type_has_post_construct_hooks (PyObject *self);
static int
gobject_run_post_construct_hooks (PyObject *self);

static PyObject *
pygi_lookup_classbuild_fn (const char *attr, PyObject **cache)
{
  if (*cache == NULL)
    {
      PyObject *modules = PySys_GetObject ("modules");
      PyObject *classbuild
          = modules ? PyDict_GetItemString (modules, "ginext.classbuild") : NULL;
      if (classbuild == NULL)
        {
          PyErr_SetString (PyExc_RuntimeError, "classbuild not loaded");
          return NULL;
        }
      *cache = PyObject_GetAttrString (classbuild, attr);
      if (*cache == NULL)
        return NULL;
    }
  return Py_NewRef (*cache);
}

static PyObject *
pygi_gobject_wrapper_factory (void)
{
  static PyObject *cached = NULL;
  return pygi_lookup_classbuild_fn ("wrap_object_from_c", &cached);
}

static PyObject *
pygi_preallocated_gobject_wrapper_factory (void)
{
  static PyObject *cached = NULL;
  return pygi_lookup_classbuild_fn ("wrap_preallocated_object_from_c", &cached);
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
pygi_gobject_check (PyObject *wrapper)
{
  return pygi_gobject_type != NULL && PyObject_TypeCheck (wrapper, pygi_gobject_type);
}

static PyObject *
gobject_new_instance (PyObject *type)
{
  if (!PyType_Check (type))
    {
      PyErr_SetString (PyExc_TypeError, "expected GObject subclass");
      return NULL;
    }

  PyTypeObject *wrapper_type = (PyTypeObject *)type;
  if (pygi_gobject_type != NULL && !PyType_IsSubtype (wrapper_type, pygi_gobject_type))
    {
      PyErr_SetString (PyExc_TypeError, "expected GObject subclass");
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

  PyGIGObject *base = (PyGIGObject *)self;
  base->construction_ptr = object;
  Py_XSETREF (base->construction_handlers, handler_dict);
  return 0;
}

/* Set each (name, value) from a properties dict on an already-constructed
 * GObject, normalizing foo_bar -> foo-bar. The dict is iterated directly (the
 * caller — tp_init — owns it and never mutates it during the call). */
static int
apply_construction_properties (GObject *object, PyObject *properties)
{
  Py_ssize_t pos = 0;
  PyObject *key = NULL;
  PyObject *value = NULL;
  while (PyDict_Next (properties, &pos, &key, &value))
    {
      PyObject *norm = PyObject_CallMethod (key, "replace", "ss", "_", "-");
      if (norm == NULL)
        return -1;
      const char *name = PyUnicode_AsUTF8 (norm);
      int r = name != NULL
                  ? pygi_gobject_set_property_on_object (object, name, value)
                  : -1;
      Py_DECREF (norm);
      if (r != 0)
        return -1;
    }
  return 0;
}

static int
bind_wrapper_to_object (PyObject *self, GObject *object, gboolean owns_ref)
{
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

static int
bind_wrapper_from_source (PyObject *self, PyObject *source, gboolean owns_ref)
{
  GObject *object = gobject_from_source (source);
  if (object == NULL && PyErr_Occurred ())
    return -1;
  return bind_wrapper_to_object (self, object, owns_ref);
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
    {
      PyObject *fnd_factory = pygi_gobject_wrapper_factory ();
      if (fnd_factory == NULL)
        return NULL;
      PyObject *fnd = pygi_fundamental_to_py (object, GI_TRANSFER_NOTHING, fnd_factory);
      Py_DECREF (fnd_factory);
      return fnd;
    }
  PyObject *factory = pygi_preallocated_gobject_wrapper_factory ();
  if (factory == NULL)
    return NULL;
  g_object_ref (object);
  PyObject *wrapper = pygi_wrap_gobject_with_factory (object, G_OBJECT_TYPE (object), factory);
  g_object_unref (object);
  Py_DECREF (factory);
  return wrapper;
}

static int
GObject_traverse (PyObject *self, visitproc visit, void *arg)
{
  Py_VISIT (((PyGIGObject *)self)->construction_handlers);
  return PyObject_VisitManagedDict (self, visit, arg);
}

static int
GObject_clear (PyObject *self)
{
  PyGIGObject *base = (PyGIGObject *)self;
  base->construction_ptr = NULL;
  Py_CLEAR (base->construction_handlers);
  PyObject_ClearManagedDict (self);
  return 0;
}

static PyObject *
GObject_prime_construction_state (PyObject *self, PyObject *args)
{
  PyObject *source = NULL;
  PyObject *handlers = Py_None;
  if (!PyArg_ParseTuple (args, "O|O:prime_construction_state", &source, &handlers))
    return NULL;

  if (prime_construction_state_from_source (self, source, handlers) < 0)
    return NULL;
  Py_RETURN_NONE;
}

/* Construct a GObject for `type`, returning a new owned reference. Bracketed by
 * the python-construction-depth flag so the construction callback during
 * g_object_new binds this wrapper rather than auto-creating one. */
static GObject *
gobject_construct_for_type (PyObject *type, PyObject *properties)
{
  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (type, &gtype) != 0)
    return NULL;
  int depth = python_construction_depth ();
  if (depth < 0 || set_python_construction_depth (depth + 1) < 0)
    return NULL;
  GObject *object = pygi_construct_gobject_object (gtype, properties);
  set_python_construction_depth (depth);
  return object;
}

static PyObject *
GObject_construct_with_properties (PyObject *type, PyObject *args)
{
  PyObject *properties = NULL;
  if (!PyArg_ParseTuple (args, "O!:construct_with_properties", &PyDict_Type, &properties))
    return NULL;
  GObject *object = gobject_construct_for_type (type, properties);
  if (object == NULL)
    return NULL;
  PyObject *ptr = PyLong_FromVoidPtr (object);
  if (ptr == NULL)
    {
      g_object_unref (object);
      return NULL;
    }
  return ptr;
}

static PyObject *
GObject_connect_constructor_handler (PyObject *self, PyObject *args)
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
GObject_signal_is_action (PyObject *self, PyObject *args)
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
GObject_signal_connect (PyObject *self, PyObject *args)
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
GObject_signal_emit (PyObject *self, PyObject *args)
{
  const char *signal_name = NULL;
  PyObject *signal_info_capsule = Py_None;
  PyObject *emit_args = Py_None;
  if (!PyArg_ParseTuple (args, "s|OO:signal_emit", &signal_name, &signal_info_capsule, &emit_args))
    return NULL;
  return pygi_signal_emit_full (self, signal_name, signal_info_capsule, emit_args);
}

static PyObject *
GObject_signal_emit_with_gtypes (PyObject *self, PyObject *args)
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
GObject_bind_from_c (PyObject *self, PyObject *args, PyObject *kwargs)
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
GObject_new_bound_from_c (PyObject *type, PyObject *args, PyObject *kwargs)
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

  PyObject *self = gobject_new_instance (type);
  if (self == NULL)
    return NULL;

  /* Bind an existing C pointer and run post-construct hooks — the C equivalent
   * of the old Python wrap_existing_pointer_for_class. */
  if (bind_wrapper_from_source (self, source, owns_ref) < 0
      || gobject_run_post_construct_hooks (self) < 0)
    {
      Py_DECREF (self);
      return NULL;
    }
  return self;
}

static PyObject *
GObject_new_preallocated_from_c (PyObject *type, PyObject *args, PyObject *kwargs)
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

  PyObject *self = gobject_new_instance (type);
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
GObject_is_bound (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  return PyBool_FromLong (((PyGIGObject *)self)->ptr != NULL);
}

static PyObject *
GObject_owns_ref (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  gboolean owns_ref = FALSE;
  pygi_gobject_wrapper_local_owns_ref (self, &owns_ref);
  return PyBool_FromLong (owns_ref);
}

static PyObject *
GObject_pointer_value (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "pointer_value");
  if (object == NULL)
    return NULL;
  return PyLong_FromVoidPtr (object);
}

static PyObject *
GObject_release_ref (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "release_ref");
  if (object == NULL)
    return NULL;

  g_object_unref (object);
  Py_RETURN_NONE;
}

static PyObject *
GObject_preserve_wrapper_state (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  store_wrapper_state_if_object_survives (self);
  Py_RETURN_NONE;
}

static PyObject *
GObject_ref_sink (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "ref_sink");
  if (object == NULL)
    return NULL;

  g_object_ref_sink (object);
  Py_RETURN_NONE;
}

static PyObject *
GObject_make_floating (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "make_floating");
  if (object == NULL)
    return NULL;

  g_object_force_floating (object);
  Py_RETURN_NONE;
}

static PyObject *
GObject_ref_count (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "ref_count");
  if (object == NULL)
    return NULL;

  return PyLong_FromSize_t (object->ref_count);
}

static PyObject *
GObject_is_floating (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "is_floating");
  if (object == NULL)
    return NULL;

  return PyBool_FromLong (g_object_is_floating (object));
}

static PyObject *
GObject_freeze_notify (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "freeze_notify");
  if (object == NULL)
    return NULL;

  g_object_freeze_notify (object);
  Py_RETURN_NONE;
}

static PyObject *
GObject_thaw_notify (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "thaw_notify");
  if (object == NULL)
    return NULL;

  g_object_thaw_notify (object);
  Py_RETURN_NONE;
}

static PyObject *
GObject_run_dispose (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  GObject *object = bound_gobject_from_self (self, "run_dispose");
  if (object == NULL)
    return NULL;

  g_object_run_dispose (object);
  Py_RETURN_NONE;
}

static PyObject *
GObject_disconnect_handler_id (PyObject *self, PyObject *args)
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
GObject_handler_id_is_connected (PyObject *self, PyObject *args)
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
GObject_stop_emission_by_name (PyObject *self, PyObject *args)
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
GObject_get_property_by_name (PyObject *self, PyObject *args)
{
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "s:get_property_by_name", &name))
    return NULL;
  return pygi_gobject_get_property_by_name (self, name);
}

static PyObject *
GObject_set_property_by_name (PyObject *self, PyObject *args)
{
  const char *name = NULL;
  PyObject *py_value = NULL;
  if (!PyArg_ParseTuple (args, "sO:set_property_by_name", &name, &py_value))
    return NULL;
  return pygi_gobject_set_property_by_name (self, name, py_value);
}

static PyObject *
GObject_from_c (PyObject *type G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source = NULL;
  if (!PyArg_ParseTuple (args, "O:from_c", &source))
    return NULL;
  return wrap_gobject_from_source (source);
}


static PyMethodDef GObject_methods[] = {
  { "construct_with_properties",
    GObject_construct_with_properties,
    METH_CLASS | METH_VARARGS,
    NULL },
  { "new_bound_from_c",
    (PyCFunction)(void (*) (void))GObject_new_bound_from_c,
    METH_CLASS | METH_VARARGS | METH_KEYWORDS,
    NULL },
  { "new_preallocated_from_c",
    (PyCFunction)(void (*) (void))GObject_new_preallocated_from_c,
    METH_CLASS | METH_VARARGS | METH_KEYWORDS,
    NULL },
  { "bind_from_c",
    (PyCFunction)(void (*) (void))GObject_bind_from_c,
    METH_VARARGS | METH_KEYWORDS,
    NULL },
  { "is_bound", GObject_is_bound, METH_NOARGS, NULL },
  { "owns_ref", GObject_owns_ref, METH_NOARGS, NULL },
  { "pointer_value", GObject_pointer_value, METH_NOARGS, NULL },
  { "release_ref", GObject_release_ref, METH_NOARGS, NULL },
  { "preserve_wrapper_state", GObject_preserve_wrapper_state, METH_NOARGS, NULL },
  { "ref_sink", GObject_ref_sink, METH_NOARGS, NULL },
  { "make_floating", GObject_make_floating, METH_NOARGS, NULL },
  { "ref_count", GObject_ref_count, METH_NOARGS, NULL },
  { "is_floating", GObject_is_floating, METH_NOARGS, NULL },
  { "freeze_notify", GObject_freeze_notify, METH_NOARGS, NULL },
  { "thaw_notify", GObject_thaw_notify, METH_NOARGS, NULL },
  { "run_dispose", GObject_run_dispose, METH_NOARGS, NULL },
  { "disconnect_handler_id", GObject_disconnect_handler_id, METH_VARARGS, NULL },
  { "handler_id_is_connected", GObject_handler_id_is_connected, METH_VARARGS, NULL },
  { "stop_emission_by_name", GObject_stop_emission_by_name, METH_VARARGS, NULL },
  { "get_property_by_name", GObject_get_property_by_name, METH_VARARGS, NULL },
  { "set_property_by_name", GObject_set_property_by_name, METH_VARARGS, NULL },
  { "from_c", GObject_from_c, METH_CLASS | METH_VARARGS, NULL },
  { "prime_construction_state", GObject_prime_construction_state, METH_VARARGS, NULL },
  { "connect_constructor_handler", GObject_connect_constructor_handler, METH_VARARGS, NULL },
  { "signal_is_action", GObject_signal_is_action, METH_VARARGS, NULL },
  { "signal_connect", GObject_signal_connect, METH_VARARGS, NULL },
  { "signal_emit", GObject_signal_emit, METH_VARARGS, NULL },
  { "signal_emit_with_gtypes", GObject_signal_emit_with_gtypes, METH_VARARGS, NULL },
  { NULL, NULL, 0, NULL },
};

static PyObject *
GObject_get_grefcount (PyObject *self, void *Py_UNUSED (closure))
{
  GObject *obj = ((PyGIGObject *)self)->ptr;
  if (obj == NULL)
    return PyLong_FromLong (0);
  return PyLong_FromUnsignedLong ((unsigned long)obj->ref_count);
}

static PyGetSetDef GObject_getset[] = {
  { "__dict__", PyObject_GenericGetDict, PyObject_GenericSetDict, NULL, NULL },
  { "__grefcount__", GObject_get_grefcount, NULL, NULL, NULL },
  { NULL },
};

static void
GObject_dealloc (PyObject *self)
{
  /* Run __del__ (drops the GObject ref); no-op if already finalized. */
  if (PyObject_CallFinalizerFromDealloc (self) < 0)
    return;
  PyObject_GC_UnTrack (self);
  PyObject_ClearWeakRefs (self);
  GObject_clear (self);
  ((PyGIGObject *)self)->ptr = NULL;
  ((PyGIGObject *)self)->flags = 0;
  ((PyGIGObject *)self)->weakreflist = NULL;
  ((PyGIGObject *)self)->construction_ptr = NULL;
  ((PyGIGObject *)self)->construction_handlers = NULL;
  Py_TYPE (self)->tp_free (self);
}

static PyObject *
GObject_repr (PyObject *self)
{
  /* Native repr. The gi-compat layer installs its own __repr__ overlay (with
   * the pygobject "type at 0xADDR" form) that overrides this slot in compat
   * mode. */
  PyObject *type = (PyObject *)Py_TYPE (self);
  PyObject *module = NULL, *stripped = NULL, *name = NULL;
  PyObject *gimeta = NULL, *type_name = NULL, *result = NULL;

  module = PyObject_GetAttrString (type, "__module__");
  if (module == NULL || !PyUnicode_Check (module))
    {
      PyErr_Clear ();
      Py_XDECREF (module);
      module = PyUnicode_FromString ("");
      if (module == NULL)
        return NULL;
    }
  stripped = PyObject_CallMethod (module, "removeprefix", "s", "ginext.");
  if (stripped == NULL)
    goto done;
  Py_SETREF (stripped,
             PyObject_CallMethod (stripped, "removeprefix", "s", "gi.repository."));
  if (stripped == NULL)
    goto done;

  name = PyObject_GetAttrString (type, "__name__");
  if (name == NULL)
    goto done;
  gimeta = PyObject_GetAttrString (type, "gimeta");
  if (gimeta == NULL)
    goto done;
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    type_name = Py_XNewRef (((GIMetaObject *)gimeta)->type_name);
  else
    type_name = PyObject_GetAttrString (gimeta, "type_name");
  if (type_name == NULL)
    goto done;

  if (((PyGIGObject *)self)->ptr == NULL)
    result = PyUnicode_FromFormat ("<%U.%U object at %p (%U unbound)>", stripped,
                                   name, self, type_name);
  else
    result = PyUnicode_FromFormat ("<%U.%U object at %p (%U)>", stripped, name,
                                   self, type_name);
done:
  Py_XDECREF (module);
  Py_XDECREF (stripped);
  Py_XDECREF (name);
  Py_XDECREF (gimeta);
  Py_XDECREF (type_name);
  return result;
}

static void
GObject_finalize (PyObject *self)
{
  PyObject *etype, *evalue, *etb;
  PyErr_Fetch (&etype, &evalue, &etb);

  if (((PyGIGObject *)self)->ptr != NULL)
    {
      gboolean owns_ref = FALSE;
      pygi_gobject_wrapper_local_owns_ref (self, &owns_ref);
      if (owns_ref)
        {
          Py_XDECREF (GObject_preserve_wrapper_state (self, NULL));
          /* Native finalization. The gi-compat layer installs a __del__ overlay
           * (the pygobject do_dispose dance) that overrides this slot in compat
           * mode. Raw C unref (not the introspected GObject.Object.unref):
           * finalize runs during interpreter shutdown when imports would fail. */
          Py_XDECREF (GObject_release_ref (self, NULL));
          if (PyErr_Occurred ())
            PyErr_Clear ();
        }
    }

  PyErr_Restore (etype, evalue, etb);
}

/* Lazily import (and cache) _finish_construction from gobjectclass: it runs the
 * post-construct hooks (Gtk.Template) and on_* handler wiring (difflib hints +
 * inspect arg counting), kept in Python. Only called when there are handlers or
 * the type has post-construct hooks. */
/* Foundational GObject.Object instance hooks live in
 * ginext.gobject.gobjectclass; C looks them up via sys.modules on demand. */

/* Split construction kwargs into (properties, handlers): keys "on_<signal>"
 * become handler entries (on_ prefix stripped); the rest are properties with
 * normalized "foo_bar" -> "foo-bar" names. */
static int
split_construction_kwargs (PyObject *kwds, PyObject **out_properties,
                           PyObject **out_handlers)
{
  PyObject *properties = PyDict_New ();
  PyObject *handlers = PyDict_New ();
  if (properties == NULL || handlers == NULL)
    goto error;
  if (kwds != NULL)
    {
      Py_ssize_t pos = 0;
      PyObject *key, *value;
      while (PyDict_Next (kwds, &pos, &key, &value))
        {
          Py_ssize_t len = 0;
          const char *k = PyUnicode_AsUTF8AndSize (key, &len);
          if (k == NULL)
            goto error;
          if (len > 3 && k[0] == 'o' && k[1] == 'n' && k[2] == '_')
            {
              PyObject *signal_name = PyUnicode_FromStringAndSize (k + 3, len - 3);
              if (signal_name == NULL)
                goto error;
              int r = PyDict_SetItem (handlers, signal_name, value);
              Py_DECREF (signal_name);
              if (r < 0)
                goto error;
            }
          /* Property names stay raw here; the construct core and
           * apply_construction_properties normalize foo_bar -> foo-bar. */
          else if (PyDict_SetItem (properties, key, value) < 0)
            goto error;
        }
    }
  *out_properties = properties;
  *out_handlers = handlers;
  return 0;
error:
  Py_XDECREF (properties);
  Py_XDECREF (handlers);
  return -1;
}

/* Whether self's type registered post-construct hooks (e.g. Gtk.Template):
 * gimeta.extensions["core"]["post_construct_hooks"]. */
static int
gobject_type_has_post_construct_hooks (PyObject *self)
{
  PyObject *gimeta = PyObject_GetAttrString ((PyObject *)Py_TYPE (self), "gimeta");
  if (gimeta == NULL)
    {
      PyErr_Clear ();
      return 0;
    }
  PyObject *extensions;
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    extensions = Py_XNewRef (((GIMetaObject *)gimeta)->extensions);
  else
    extensions = PyObject_GetAttrString (gimeta, "extensions");
  Py_DECREF (gimeta);
  if (extensions == NULL)
    {
      PyErr_Clear ();
      return 0;
    }
  int result = 0;
  if (PyDict_Check (extensions))
    {
      PyObject *core = PyDict_GetItemString (extensions, "core"); /* borrowed */
      if (core != NULL && PyDict_Check (core))
        {
          PyObject *hooks = PyDict_GetItemString (core, "post_construct_hooks");
          if (hooks != NULL && PyObject_IsTrue (hooks) == 1)
            result = 1;
        }
    }
  Py_DECREF (extensions);
  return result;
}

/* Look up gobjectclass._finish_construction — cached after first call. */
static PyObject *
gobject_finish_construction_attr (void)
{
  static PyObject *cached = NULL;
  if (cached == NULL)
    {
      PyObject *modules = PySys_GetObject ("modules");
      PyObject *gobjectclass
          = modules ? PyDict_GetItemString (modules, "ginext.gobject.gobjectclass") : NULL;
      if (gobjectclass == NULL)
        {
          PyErr_SetString (PyExc_RuntimeError, "gobjectclass not loaded");
          return NULL;
        }
      cached = PyObject_GetAttrString (gobjectclass, "_finish_construction");
      if (cached == NULL)
        return NULL;
    }
  return Py_NewRef (cached);
}

/* Run the type's post-construct hooks (Gtk.Template) via _finish_construction
 * with no handlers. No-op (no Python call) when the type has no hooks. */
static int
gobject_run_post_construct_hooks (PyObject *self)
{
  if (!gobject_type_has_post_construct_hooks (self))
    return 0;
  PyObject *finish = gobject_finish_construction_attr ();
  if (finish == NULL)
    return -1;
  PyObject *empty = PyDict_New ();
  if (empty == NULL)
    return -1;
  PyObject *r = PyObject_CallFunctionObjArgs (finish, self, empty, NULL);
  Py_DECREF (empty);
  Py_DECREF (finish);
  if (r == NULL)
    return -1;
  Py_DECREF (r);
  return 0;
}

/* tp_init: GObject construction in C. _finish_construction (Python) is only
 * invoked when there are on_* handlers or the type has post-construct hooks. */
static int
GObject_init (PyObject *self, PyObject *args, PyObject *kwds)
{
  if (args != NULL && PyTuple_GET_SIZE (args) != 0)
    {
      PyErr_SetString (PyExc_TypeError,
                       "GObject.Object() takes no positional arguments");
      return -1;
    }

  PyObject *properties = NULL, *handlers = NULL;
  if (split_construction_kwargs (kwds, &properties, &handlers) < 0)
    return -1;

  int rc = -1;
  gboolean owns_ref;
  GObject *object;
  PyObject *pending = NULL; /* deferred: handlers primed by C, owned */
  PyObject *finish_handlers = NULL;
  PyGIGObject *base = (PyGIGObject *)self;

  if (base->construction_ptr == NULL)
    {
      /* Normal path: g_object_new, owning the ref. */
      object = gobject_construct_for_type ((PyObject *)Py_TYPE (self), properties);
      if (object == NULL)
        goto done;
      owns_ref = TRUE;
    }
  else
    {
      /* Deferred-shell path (C-initiated python subclass): consume the primed
       * construction state, apply any kwargs, bind without owning the ref. */
      pending = base->construction_handlers; /* owned; may be NULL */
      object = base->construction_ptr;
      base->construction_ptr = NULL;
      base->construction_handlers = NULL;
      if (PyDict_GET_SIZE (properties) > 0
          && apply_construction_properties (object, properties) < 0)
        goto done;
      owns_ref = FALSE;
    }

  if (bind_wrapper_to_object (self, object, owns_ref) < 0)
    {
      if (owns_ref)
        g_object_unref (object); /* construct gave us a ref; bind didn't take it */
      goto done;
    }

  /* Handlers to wire: the on_* kwargs, merged onto any primed by the deferred
   * path. */
  if (pending != NULL)
    {
      finish_handlers = pending;
      pending = NULL;
      if (PyDict_Update (finish_handlers, handlers) < 0)
        goto done;
    }
  else
    finish_handlers = Py_NewRef (handlers);

  if (PyDict_GET_SIZE (finish_handlers) > 0
      || gobject_type_has_post_construct_hooks (self))
    {
      PyObject *finish = gobject_finish_construction_attr ();
      if (finish == NULL)
        goto done;
      PyObject *r = PyObject_CallFunctionObjArgs (finish, self, finish_handlers, NULL);
      Py_DECREF (finish);
      if (r == NULL)
        goto done;
      Py_DECREF (r);
    }
  rc = 0;

done:
  Py_XDECREF (properties);
  Py_XDECREF (handlers);
  Py_XDECREF (pending);
  Py_XDECREF (finish_handlers);
  return rc;
}

/* tp_getattro: normal attribute lookup, then the registered __getattr__ body
 * (pspec synthesis, signal access, compat shims) on a genuine miss. */
static PyObject *
GObject_getattro (PyObject *self, PyObject *name)
{
  PyObject *result = PyObject_GenericGetAttr (self, name);
  if (result != NULL || !PyErr_ExceptionMatches (PyExc_AttributeError))
    return result;
  static PyObject *getattr_fn = NULL;
  if (getattr_fn == NULL)
    {
      PyObject *modules = PySys_GetObject ("modules");
      PyObject *mod
          = modules ? PyDict_GetItemString (modules, "ginext.gobject.gobjectclass") : NULL;
      if (mod != NULL)
        getattr_fn = PyObject_GetAttrString (mod, "_obj_getattr");
    }
  if (getattr_fn == NULL)
    {
      PyErr_SetObject (PyExc_AttributeError, name);
      return NULL;
    }
  PyErr_Clear ();
  return PyObject_CallFunctionObjArgs (getattr_fn, self, name, NULL);
}

/* tp_setattro: route writes through the registered __setattr__ body (which
 * synthesizes a pspec descriptor for introspected properties before the set).
 * Deletes — and writes before registration — fall back to the generic path. */
static int
GObject_setattro (PyObject *self, PyObject *name, PyObject *value)
{
  if (value == NULL)
    return PyObject_GenericSetAttr (self, name, value);
  static PyObject *setattr_fn = NULL;
  if (setattr_fn == NULL)
    {
      PyObject *modules = PySys_GetObject ("modules");
      PyObject *mod
          = modules ? PyDict_GetItemString (modules, "ginext.gobject.gobjectclass") : NULL;
      if (mod != NULL)
        setattr_fn = PyObject_GetAttrString (mod, "_obj_setattr");
    }
  if (setattr_fn == NULL)
    return PyObject_GenericSetAttr (self, name, value);
  PyObject *r = PyObject_CallFunctionObjArgs (setattr_fn, self, name, value, NULL);
  if (r == NULL)
    return -1;
  Py_DECREF (r);
  return 0;
}

static PyType_Slot GinextGObject_slots[] = {
  { Py_tp_new, PyType_GenericNew },
  { Py_tp_init, GObject_init },
  { Py_tp_dealloc, GObject_dealloc },
  { Py_tp_repr, GObject_repr },
  { Py_tp_finalize, GObject_finalize },
  { Py_tp_getattro, GObject_getattro },
  { Py_tp_setattro, GObject_setattro },
  { Py_tp_traverse, GObject_traverse },
  { Py_tp_clear, GObject_clear },
  { Py_tp_methods, GObject_methods },
  { Py_tp_getset, GObject_getset },
  { 0, NULL },
};

PyType_Spec GinextGObject_spec = {
  .name = "ginext.private._gobject.GObject",
  .basicsize = sizeof (PyGIGObject),
  .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HAVE_GC | Py_TPFLAGS_MANAGED_DICT,
  .slots = GinextGObject_slots,
};

static int
wrapper_local_bound_set (PyObject *wrapper, gboolean bound)
{
  if (!pygi_gobject_check (wrapper))
    return 0;
  PyGIGObject *base = (PyGIGObject *)wrapper;
  if (!bound)
    base->ptr = NULL;
  return 0;
}

int
pygi_gobject_wrapper_local_bound (PyObject *wrapper, gboolean *bound)
{
  if (!pygi_gobject_check (wrapper))
    return 0;
  *bound = ((PyGIGObject *)wrapper)->ptr != NULL;
  return 1;
}

static void
wrapper_local_bound_clear (PyObject *wrapper)
{
  if (!pygi_gobject_check (wrapper))
    return;
  ((PyGIGObject *)wrapper)->ptr = NULL;
}

static int
wrapper_local_owns_ref_set (PyObject *wrapper, gboolean owns_ref)
{
  if (!pygi_gobject_check (wrapper))
    return 0;
  PyGIGObject *base = (PyGIGObject *)wrapper;
  if (owns_ref)
    base->flags |= PYGI_GOBJECT_WRAPPER_OWNS_REF;
  else
    base->flags &= ~PYGI_GOBJECT_WRAPPER_OWNS_REF;
  return 0;
}

static int
wrapper_local_owns_ref_get (PyObject *wrapper, gboolean *owns_ref)
{
  if (!pygi_gobject_check (wrapper))
    return 0;
  *owns_ref = ((((PyGIGObject *)wrapper)->flags & PYGI_GOBJECT_WRAPPER_OWNS_REF) != 0);
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
  if (!pygi_gobject_check (wrapper))
    return;
  ((PyGIGObject *)wrapper)->flags &= ~PYGI_GOBJECT_WRAPPER_OWNS_REF;
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
  if (!pygi_gobject_check (wrapper))
    return;

  GObject *object = ((PyGIGObject *)wrapper)->ptr;
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
  if (wrapper == NULL || !pygi_gobject_check (wrapper))
    return NULL;
  return ((PyGIGObject *)wrapper)->ptr;
}

void
pygi_gobject_wrapper_bind_pointer (PyObject *wrapper, GObject *object)
{
  if (wrapper == NULL || !pygi_gobject_check (wrapper))
    return;
  ((PyGIGObject *)wrapper)->ptr = object;
}

void
pygi_gobject_wrapper_forget_pointer (PyObject *wrapper)
{
  if (wrapper == NULL || !pygi_gobject_check (wrapper))
    return;
  ((PyGIGObject *)wrapper)->ptr = NULL;
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

GObject *
pygi_gobject_get (PyObject *wrapper)
{
  GObject *object = pygi_gobject_wrapper_pointer (wrapper);
  if (object != NULL)
    return object;
  if (PyErr_Occurred ())
    return NULL;

  if (pygi_fundamental_check (wrapper))
    return (GObject *)pygi_fundamental_get_instance (wrapper);

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
  return pygi_raise_gobject_type_error_for_gtype_named (expected_gtype, actual, NULL);
}

int
pygi_raise_gobject_type_error_for_gtype_named (GType expected_gtype,
                                               PyObject *actual,
                                               const char *arg_name)
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

  if (arg_name != NULL)
    PyErr_Format (PyExc_TypeError, "%s: expected %U, but got %U",
                  arg_name, expected, actual_repr);
  else
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
    {
      PyObject *fnd_factory = pygi_gobject_wrapper_factory ();
      if (fnd_factory == NULL)
        return NULL;
      PyObject *fnd = pygi_fundamental_to_py (object, transfer, fnd_factory);
      Py_DECREF (fnd_factory);
      return fnd;
    }

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

  PyObject *factory = NULL;

  /* Fast path: when the requested wrapper gtype matches the object's actual
   * gtype and the registry has a plain GObject subclass for it, bind directly
   * via type.new_bound_from_c(ptr) — no Python wrapper-factory dispatch. */
  if (wrapper_gtype == G_OBJECT_TYPE (object) && pygi_gobject_type != NULL
      && pygi_namespace_context () == Py_None)
    {
      PyTypeObject *py_type = pygi_lookup_gtype_pytype (wrapper_gtype);
      if (py_type != NULL && PyType_IsSubtype (py_type, pygi_gobject_type))
        {
          PyObject *ptr_obj = PyLong_FromVoidPtr (object);
          if (ptr_obj == NULL)
            goto error;
          PyObject *direct = PyObject_CallMethod ((PyObject *)py_type,
                                                  "new_bound_from_c", "O", ptr_obj);
          Py_DECREF (ptr_obj);
          if (direct != NULL)
            return direct;
          goto error; /* ref released in error path */
        }
    }

  factory = pygi_gobject_wrapper_factory ();
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
          Py_DECREF (factory);
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
  Py_DECREF (factory);
  if (wrapper == NULL)
    {
      g_object_unref (object);
      return NULL;
    }
  return wrapper;

error:
  Py_XDECREF (factory);
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
    {
      PyObject *fnd_factory = pygi_gobject_wrapper_factory ();
      if (fnd_factory == NULL)
        return NULL;
      PyObject *fnd = pygi_fundamental_to_py (object, GI_TRANSFER_NOTHING, fnd_factory);
      Py_DECREF (fnd_factory);
      return fnd;
    }
  PyObject *factory = pygi_preallocated_gobject_wrapper_factory ();
  if (factory == NULL)
    return NULL;
  PyObject *result = pygi_wrap_gobject_with_factory (object, wrapper_gtype, factory);
  Py_DECREF (factory);
  return result;
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
