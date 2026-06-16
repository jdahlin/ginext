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

/* `_gobject` Python module — PyInit and the methods table. Each method
 * lives in its own .c (one per exported function); this file just lists
 * them and stands up the GIMeta heap type. New per-function .c files
 * declare their entry points extern; add the prototype here and a line
 * to the methods table.
 */
#include "common.h"
#include "GObject/hooks.h"
#include "GObject/coercions.h"
#include "marshal/conversion.h"
#include "GObject/Closure.h"
#include "GObject/property-descr.h"
#include "GObject/Fundamental.h"
#include "GObject/Object-info.h"
#include "GObject/Object-weakref.h"
#include "GObject/Object.h"
#include "GObject/ObjectMeta.h"
#include "GObject/GIMeta.h"
#include "GObject/vfunc-descr.h"
#include "GIRepository/BaseInfo.h"
#include "GIRepository/Info.h"
#include "runtime/callable.h"

extern PyType_Spec ReverseCallback_spec;
extern PyTypeObject *ginext_reverse_callback_type;
extern PyObject *
py_installed_versions (PyObject *m, PyObject *args);
extern PyObject *
py_require_namespace (PyObject *m, PyObject *args);
extern PyObject *
py_namespace_find (PyObject *m, PyObject *args);
extern PyObject *
py_namespace_dir (PyObject *m, PyObject *args);
extern PyObject *
py_glib_event_source_new (PyObject *m, PyObject *args);
extern PyObject *
py_record_setup_class (PyObject *m, PyObject *args);
extern PyObject *
py_register_gtype_pytype (PyObject *m, PyObject *args);
extern PyObject *
py_build_callable_descriptor (PyObject *m, PyObject *args);
extern PyObject *
py_invoke_callable_descriptor (PyObject *m,
                               PyObject *const *args,
                               Py_ssize_t nargs,
                               PyObject *kwnames);
extern PyObject *
py_class_struct_wrapper (PyObject *m, PyObject *args);
extern PyObject *
py_invoke_by_name (PyObject *m, PyObject *const *args, Py_ssize_t nargs);
extern PyObject *
py_synthetic_callable (PyObject *m, PyObject *args);
extern PyObject *
py_callable_async_info (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_get_type (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_get_gtype (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_init_value (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_unset_value (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_reset_value (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_get_value (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_set_value (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_set_data_int (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_set_data_uint64 (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_wrap_pointer (PyObject *m, PyObject *args);
extern PyObject *
py_gstrv_get_type (PyObject *m, PyObject *args);
extern PyObject *
py_type_has_value_table (PyObject *m, PyObject *args);
PyObject *
py_register_static (PyObject *m, PyObject *args);
extern PyObject *
py_param_spec_info (PyObject *m, PyObject *args);
extern PyObject *
py_param_spec_default_value (PyObject *m, PyObject *args);
extern PyObject *
py_param_spec_numeric_info (PyObject *m, PyObject *args);
extern PyObject *
py_register_gobject_subclass (PyObject *m, PyObject *args);
extern PyObject *
py_object_get_property_by_name (PyObject *m, PyObject *args);
extern PyObject *
py_register_property_type_info (PyObject *m, PyObject *args);
extern PyObject *
py_register_signal (PyObject *m, PyObject *args);
extern PyType_Spec PyGIGLibBoxed_spec;
PyTypeObject *pygi_gboxed_base_type = NULL;
PyTypeObject *pygi_gobject_type = NULL;

static PyObject *
py_init_gobject (PyObject *m, PyObject *args)
{
  PyObject *metaclass = NULL;
  if (!PyArg_ParseTuple (args, "O:init_gobject", &metaclass))
    return NULL;
  if (!PyType_Check (metaclass))
    {
      PyErr_SetString (PyExc_TypeError, "metaclass must be a type");
      return NULL;
    }
  if (pygi_gobject_type != NULL)
    return Py_NewRef ((PyObject *)pygi_gobject_type);

  PyObject *gobject
      = PyType_FromMetaclass ((PyTypeObject *)metaclass, m, &GinextGObject_spec, NULL);
  if (gobject == NULL)
    return NULL;
  pygi_gobject_type = (PyTypeObject *)gobject;
  pygi_gobject_type->tp_weaklistoffset = offsetof (PyGIGObject, weakreflist);

  static const char *const naming[][2] = { { "__name__", "Object" },
                                           { "__qualname__", "Object" },
                                           { "__module__", "ginext.GObject" } };
  for (size_t i = 0; i < 3; i++)
    {
      PyObject *v = PyUnicode_FromString (naming[i][1]);
      if (v == NULL || PyObject_SetAttrString (gobject, naming[i][0], v) < 0)
        {
          Py_XDECREF (v);
          goto error;
        }
      Py_DECREF (v);
    }

  /* The two class variables the old _GObjectBody body carried. _gobject_is_root
   * must live in GObject.Object's own __dict__ (the metaclass keys the root-class
   * check on that); _class_struct_name defaults to None and is overridden per
   * class by classbuild. */
  if (PyObject_SetAttrString (gobject, "_class_struct_name", Py_None) < 0)
    goto error;
  if (PyObject_SetAttrString (gobject, "_gobject_is_root", Py_True) < 0)
    goto error;

  {
    GType gtype = g_type_from_name ("GObject");
    Py_AUTO_DECREF PyObject *type_name = PyUnicode_FromString ("GObject");
    Py_AUTO_DECREF PyObject *pspecs = PyDict_New ();
    Py_AUTO_DECREF PyObject *prop_ids = PyDict_New ();
    if (type_name == NULL || pspecs == NULL || prop_ids == NULL)
      goto error;
    PyObject *gimeta = gimeta_new (gtype, type_name, Py_None, pspecs, prop_ids, Py_None);
    if (gimeta == NULL)
      goto error;
    int rc = PyObject_SetAttrString (gobject, "gimeta", gimeta);
    Py_DECREF (gimeta);
    if (rc < 0)
      goto error;
  }

  if (PyModule_AddObjectRef (m, "GObject", gobject) < 0)
    goto error;
  return gobject;

error:
  pygi_gobject_type = NULL;
  Py_DECREF (gobject);
  return NULL;
}

/* Sorted by name — must stay in strcmp order for bsearch. */
typedef struct
{
  const char *name;
  PyGIHookID  id;
} HookEntry;

static const HookEntry hook_table[] = {
  { "Fundamental.getattr",           PYGI_HOOK_FUNDAMENTAL_GETATTR      },
  { "Object.getattr",                PYGI_HOOK_OBJECT_GETATTR           },
  { "Object.post_init",              PYGI_HOOK_OBJECT_POST_INIT         },
  { "Object.setattr",                PYGI_HOOK_OBJECT_SETATTR           },
  { "Object.wrap",                   PYGI_HOOK_OBJECT_WRAP              },
  { "ObjectClass.dir",               PYGI_HOOK_OBJECTCLASS_DIR          },
  { "ObjectClass.getattr",           PYGI_HOOK_OBJECTCLASS_GETATTR      },
  { "callable_signature",            PYGI_HOOK_CALLABLE_SIGNATURE       },
  { "class_from_namespace_profile",  PYGI_HOOK_CLASS_FROM_NS_PROFILE    },
  { "exception_from_gerror",         PYGI_HOOK_EXCEPTION_FROM_GERROR    },
  { "gvalue.from_py",                PYGI_HOOK_GVALUE_FROM_PY           },
  { "gvalue.to_py",                  PYGI_HOOK_GVALUE_TO_PY             },
  { "load_namespace",                PYGI_HOOK_LOAD_NAMESPACE           },
  { "packed_user_data_type",         PYGI_HOOK_PACKED_USER_DATA_TYPE    },
  { "result_tuple_new_type",         PYGI_HOOK_RESULT_TUPLE_NEW_TYPE    },
};

static int
hook_entry_cmp (const void *key, const void *entry)
{
  return strcmp ((const char *)key, ((const HookEntry *)entry)->name);
}

/* private.register_coercion(gtype, callable) — register a Python→GLib coercion for a GType.
 * gtype may be an int (raw GType), a GObject/GBoxed class, or an instance. */
static PyObject *
py_register_coercion (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj;
  PyObject *fn;
  if (!PyArg_ParseTuple (args, "OO:register_coercion", &gtype_obj, &fn))
    return NULL;
  if (!PyCallable_Check (fn))
    {
      PyErr_SetString (PyExc_TypeError, "register_coercion: fn must be callable");
      return NULL;
    }
  GType gtype = 0;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  if (pygi_coercion_register (gtype, fn) < 0)
    return NULL;
  Py_RETURN_NONE;
}

/* private.register_hook(name, callable) — append a callable to the named hook list. */
static PyObject *
py_register_hook (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  const char *name;
  PyObject *fn;
  if (!PyArg_ParseTuple (args, "sO", &name, &fn))
    return NULL;
  if (!PyCallable_Check (fn))
    {
      PyErr_SetString (PyExc_TypeError, "expected callable");
      return NULL;
    }

  const HookEntry *entry = bsearch (name, hook_table,
                                     G_N_ELEMENTS (hook_table),
                                     sizeof (HookEntry), hook_entry_cmp);
  if (entry == NULL)
    {
      PyErr_Format (PyExc_ValueError, "unknown hook name: '%s'", name);
      return NULL;
    }
  PyObject **slot = &pygi_hooks[entry->id];

  if (*slot == NULL)
    {
      *slot = PyList_New (0);
      if (*slot == NULL)
        return NULL;
    }
  if (PyList_Append (*slot, fn) < 0)
    return NULL;
  Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
  { "installed_versions", py_installed_versions, METH_NOARGS, NULL },
  { "init_gobject", py_init_gobject, METH_VARARGS, NULL },
  { "require_namespace", py_require_namespace, METH_VARARGS, NULL },
  { "namespace_find", py_namespace_find, METH_VARARGS, NULL },
  { "namespace_dir", py_namespace_dir, METH_VARARGS, NULL },
  { "glib_event_source_new", py_glib_event_source_new, METH_VARARGS, NULL },
  { "record_setup_class", py_record_setup_class, METH_VARARGS, NULL },
  { "register_gtype_pytype", py_register_gtype_pytype, METH_VARARGS, NULL },
  { "build_callable_descriptor", py_build_callable_descriptor, METH_VARARGS, NULL },
  { "invoke_callable_descriptor",
    (PyCFunction)(void (*) (void))py_invoke_callable_descriptor,
    METH_FASTCALL | METH_KEYWORDS,
    NULL },
  { "synthetic_callable", py_synthetic_callable, METH_VARARGS, NULL },
  { "callable_async_info", py_callable_async_info, METH_VARARGS, NULL },
  { "class_struct_wrapper", py_class_struct_wrapper, METH_VARARGS, NULL },
  { "invoke", (PyCFunction)(void (*) (void))py_invoke_by_name, METH_FASTCALL, NULL },
  { "gvalue_get_type", py_gvalue_get_type, METH_VARARGS, NULL },
  { "gvalue_get_gtype", py_gvalue_get_gtype, METH_VARARGS, NULL },
  { "gvalue_init_value", py_gvalue_init_value, METH_VARARGS, NULL },
  { "gvalue_unset_value", py_gvalue_unset_value, METH_VARARGS, NULL },
  { "gvalue_reset_value", py_gvalue_reset_value, METH_VARARGS, NULL },
  { "gvalue_get_value", py_gvalue_get_value, METH_VARARGS, NULL },
  { "gvalue_set_value", py_gvalue_set_value, METH_VARARGS, NULL },
  { "gvalue_set_data_int", py_gvalue_set_data_int, METH_VARARGS, NULL },
  { "gvalue_set_data_uint64", py_gvalue_set_data_uint64, METH_VARARGS, NULL },
  { "gvalue_wrap_pointer", py_gvalue_wrap_pointer, METH_VARARGS, NULL },
  { "gobject_add_weak_notify", py_gobject_add_weak_notify, METH_VARARGS, NULL },
  { "gobject_get_property_by_name", py_object_get_property_by_name, METH_VARARGS, NULL },
  /* DROP-ish: GLib.strv_get_type exists, but GType.STRV is set at gobject.py
           module load where importing GLib is circular — defer that constant first */
  { "gstrv_get_type", py_gstrv_get_type, METH_VARARGS, NULL },
  { "type_has_value_table", py_type_has_value_table, METH_VARARGS, NULL },
  { "register_static", py_register_static, METH_VARARGS, NULL },
  { "param_spec_info", py_param_spec_info, METH_VARARGS, NULL },
  { "param_spec_default_value", py_param_spec_default_value, METH_VARARGS, NULL },
  { "param_spec_numeric_info", py_param_spec_numeric_info, METH_VARARGS, NULL },
  { "register_gobject_subclass", py_register_gobject_subclass, METH_VARARGS, NULL },
  { "register_property_type_info", py_register_property_type_info, METH_VARARGS, NULL },
  { "register_signal", py_register_signal, METH_VARARGS, NULL },
  { "register_hook", py_register_hook, METH_VARARGS, NULL },
  { "register_coercion", py_register_coercion, METH_VARARGS, NULL },
  { NULL }
};

static void
ginext_module_free (void *module G_GNUC_UNUSED)
{
  pygi_callback_closure_drain_deferred_frees ();
}

static struct PyModuleDef moddef = {
  PyModuleDef_HEAD_INIT, .m_name = "_gobject",         .m_size = -1,
  .m_methods = methods,  .m_free = ginext_module_free,
};

PyMODINIT_FUNC
PyInit__gobject (void)
{
  if (PyType_Ready (&GIMetaType) < 0)
    return NULL;
  if (PyType_Ready (&GinextPropertyDescriptorType) < 0)
    return NULL;

  PyObject *m = PyModule_Create (&moddef);
  if (!m)
    return NULL;

#ifdef Py_GIL_DISABLED
  PyUnstable_Module_SetGIL (m, Py_MOD_GIL_NOT_USED);
#endif

  PyObject *boxed_type = PyType_FromSpec (&PyGIGLibBoxed_spec);
  if (boxed_type == NULL)
    {
      Py_DECREF (m);
      return NULL;
    }
  pygi_gboxed_base_type = (PyTypeObject *)boxed_type;
  if (PyModule_AddObject (m, "GBoxed", boxed_type) < 0)
    {
      Py_DECREF (boxed_type);
      Py_DECREF (m);
      return NULL;
    }

  /* GObject.Object is created later via init_gobject(GObjectMeta). The
   * GObjectMeta metatype is created here so it exists for that call. */
  if (pygi_create_gobjectmeta (m) == NULL)
    {
      Py_DECREF (m);
      return NULL;
    }

  PyObject *callable_descriptor_type = PyType_FromSpec (&GinextCallableDescriptor_spec);
  if (callable_descriptor_type == NULL)
    {
      Py_DECREF (m);
      return NULL;
    }
  ginext_callable_descriptor_type = (PyTypeObject *)callable_descriptor_type;
  if (PyModule_AddObject (m, "CallableDescriptor", callable_descriptor_type) < 0)
    {
      Py_DECREF (callable_descriptor_type);
      Py_DECREF (m);
      return NULL;
    }

  PyObject *vfunc_wrapper_type = PyType_FromSpec (&GinextVFuncDescriptor_spec);
  if (vfunc_wrapper_type == NULL)
    {
      Py_DECREF (m);
      return NULL;
    }
  ginext_vfunc_wrapper_type = (PyTypeObject *)vfunc_wrapper_type;
  if (PyModule_AddObject (m, "VFuncDescriptor", vfunc_wrapper_type) < 0)
    {
      Py_DECREF (vfunc_wrapper_type);
      Py_DECREF (m);
      return NULL;
    }

  PyObject *reverse_callback_type = PyType_FromSpec (&ReverseCallback_spec);
  if (reverse_callback_type == NULL)
    {
      Py_DECREF (m);
      return NULL;
    }
  ginext_reverse_callback_type = (PyTypeObject *)reverse_callback_type;

  Py_INCREF (&GIMetaType);
  if (PyModule_AddObject (m, "GIMeta", (PyObject *)&GIMetaType) < 0)
    {
      Py_DECREF (&GIMetaType);
      Py_DECREF (m);
      return NULL;
    }
  Py_INCREF (&GinextPropertyDescriptorType);
  if (PyModule_AddObject (m, "PropertyDescriptor", (PyObject *)&GinextPropertyDescriptorType) < 0)
    {
      Py_DECREF (&GinextPropertyDescriptorType);
      Py_DECREF (m);
      return NULL;
    }

  if (ginext_register_info_types (m) < 0)
    {
      Py_DECREF (m);
      return NULL;
    }
  if (pygi_gobject_weakref_init (m) < 0)
    {
      Py_DECREF (m);
      return NULL;
    }

  if (pygi_fundamental_type_init () < 0)
    {
      Py_DECREF (m);
      return NULL;
    }
  Py_INCREF ((PyObject *)PyGIFundamental_Type);
  if (PyModule_AddObject (m, "Fundamental", (PyObject *)PyGIFundamental_Type) < 0)
    {
      Py_DECREF ((PyObject *)PyGIFundamental_Type);
      Py_DECREF (m);
      return NULL;
    }

  if (pygi_coercions_init () < 0)
    {
      Py_DECREF (m);
      return NULL;
    }

  return m;
}
