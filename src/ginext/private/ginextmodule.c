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
#include "GObject/Closure.h"
#include "GObject/DeclaredProperty.h"
#include "GObject/Fundamental.h"
#include "GObject/Object-info.h"
#include "GObject/Object-weakref.h"
#include "GObject/Object.h"
#include "GObject/ObjectMeta.h"
#include "GObject/GIMeta.h"
#include "GObject/Object-vfunc-wrapper.h"
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
py_namespace_is_registered (PyObject *m, PyObject *args);
extern PyObject *
py_namespace_get_dependencies (PyObject *m, PyObject *args);
extern PyObject *
py_namespace_get_immediate_dependencies (PyObject *m, PyObject *args);
extern PyObject *
py_namespace_find_by_gtype (PyObject *m, PyObject *args);
extern PyObject *
py_namespace_get_typelib_path (PyObject *m, PyObject *args);
extern PyObject *
py_instantiatable_unref (PyObject *m, PyObject *args);
extern PyObject *
py_record_new (PyObject *m, PyObject *args);
extern PyObject *
py_glib_event_source_new (PyObject *m, PyObject *args);
extern PyObject *
py_record_field_get (PyObject *m, PyObject *args);
extern PyObject *
py_record_field_set (PyObject *m, PyObject *args);
extern PyObject *
py_fundamental_from_pointer (PyObject *m, PyObject *args);
extern PyObject *
py_fundamental_init_hooks (PyObject *m, PyObject *args);
extern PyObject *
py_record_ensure_size (PyObject *m, PyObject *args);
extern PyObject *
py_record_memory_get (PyObject *m, PyObject *args);
extern PyObject *
py_record_memory_set (PyObject *m, PyObject *args);
extern PyObject *
py_record_copy (PyObject *m, PyObject *args);
extern PyObject *
py_record_pointer_equal (PyObject *m, PyObject *args);
extern PyObject *
py_record_pointer_value (PyObject *m, PyObject *args);
extern PyObject *
py_record_install_field_descriptors (PyObject *m, PyObject *args);
extern PyObject *
py_record_field_names (PyObject *m, PyObject *args);
extern PyObject *
py_register_boxed_class (PyObject *m, PyObject *args);
extern PyObject *
py_reset_invoke_stats (PyObject *m, PyObject *args);
extern PyObject *
py_invoke_stats (PyObject *m, PyObject *args);
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
py_gvalue_array_get_nth_type (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_set_value (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_set_to_py_fallback (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_get_to_py_fallback (PyObject *m, PyObject *unused);
extern PyObject *
py_gvalue_set_from_py_converter (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_get_from_py_converter (PyObject *m, PyObject *unused);
extern PyObject *
py_gvalue_set_data_int (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_set_data_uint64 (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_wrap_pointer (PyObject *m, PyObject *args);
extern PyObject *
py_gvalue_new_for_gtype (PyObject *m, PyObject *args);
extern PyObject *
py_gstrv_get_type (PyObject *m, PyObject *args);
extern PyObject *
py_gerror_get_type (PyObject *m, PyObject *args);
extern PyObject *
py_ensure_cairo_gobject_types (PyObject *m, PyObject *args);
extern PyObject *
py_type_has_value_table (PyObject *m, PyObject *args);
extern PyObject *
py_pointer_type_register_static (PyObject *m, PyObject *args);
extern PyObject *
py_param_spec_info (PyObject *m, PyObject *args);
extern PyObject *
py_param_spec_default_value (PyObject *m, PyObject *args);
extern PyObject *
py_param_spec_numeric_info (PyObject *m, PyObject *args);
extern PyType_Spec PyGIGLibBoxed_spec;
extern PyTypeObject *pygi_gboxed_base_type;

/* Test-infra: pre-loads a shared library by absolute path via g_module_open so
 * that GLib's own g_module_open("libfoo.so") later finds it already resident in
 * the dynamic-linker cache. This is needed because LD_LIBRARY_PATH changes made
 * in Python (os.environ) are not seen by dlopen — the linker reads it once at
 * process start. Calling g_module_open with an absolute path here causes the
 * linker to register the loaded handle so a subsequent open("libfoo.so") hits
 * the cache.
 */
static PyObject *
py_preload_shared_library (PyObject *m, PyObject *args)
{
  const char *path;
  if (!PyArg_ParseTuple (args, "s", &path))
    return NULL;
  GModule *mod = g_module_open (path, G_MODULE_BIND_LAZY);
  if (mod == NULL)
    {
      PyErr_SetString (PyExc_OSError, g_module_error ());
      return NULL;
    }
  Py_RETURN_NONE;
}


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

  if (PyModule_AddObjectRef (m, "GObject", gobject) < 0)
    goto error;
  return gobject;

error:
  pygi_gobject_type = NULL;
  Py_DECREF (gobject);
  return NULL;
}

/* Test-infra: thin wrappers around PyArg_ParseTuple for each numeric/string
 * format code.  Used by test_pyargs_oracle.py to verify that ginext's type
 * error messages match what CPython's argument parser produces.  These are
 * equivalent to _testcapi.getargs_<fmt> but live here so the oracle tests
 * run on release builds (no Py_DEBUG required).
 */
#define GINEXT_GETARGS_INT(name, fmt, ctype, converter)                                            \
  static PyObject *py_getargs_##name (PyObject *m, PyObject *args)                                 \
  {                                                                                                \
    ctype val;                                                                                     \
    if (!PyArg_ParseTuple (args, fmt, &val))                                                       \
      return NULL;                                                                                 \
    return converter (val);                                                                        \
  }

GINEXT_GETARGS_INT (b, "b", signed char, PyLong_FromLong)
GINEXT_GETARGS_INT (B, "B", unsigned char, PyLong_FromUnsignedLong)
GINEXT_GETARGS_INT (h, "h", short, PyLong_FromLong)
GINEXT_GETARGS_INT (H, "H", unsigned short, PyLong_FromUnsignedLong)
GINEXT_GETARGS_INT (i, "i", int, PyLong_FromLong)
GINEXT_GETARGS_INT (I, "I", unsigned int, PyLong_FromUnsignedLong)
GINEXT_GETARGS_INT (l, "l", long, PyLong_FromLong)
GINEXT_GETARGS_INT (L, "L", unsigned long long, PyLong_FromUnsignedLongLong)
GINEXT_GETARGS_INT (n, "n", Py_ssize_t, PyLong_FromSsize_t)
GINEXT_GETARGS_INT (k, "k", unsigned long, PyLong_FromUnsignedLong)
GINEXT_GETARGS_INT (K, "K", unsigned long long, PyLong_FromUnsignedLongLong)
GINEXT_GETARGS_INT (f, "f", float, PyFloat_FromDouble)
GINEXT_GETARGS_INT (d, "d", double, PyFloat_FromDouble)

#undef GINEXT_GETARGS_INT

static PyObject *
py_getargs_s (PyObject *m, PyObject *args)
{
  const char *val;
  if (!PyArg_ParseTuple (args, "s", &val))
    return NULL;
  return PyUnicode_FromString (val);
}

/* Goal: shrink this table to only what bootstraps invoke. Each entry is
 * tagged with how to remove it ("DROP: ...") or why it must stay ("keep: ...").
 * Anything that is just an introspected GObject/GLib call should route through
 * `invoke` once invoke grows the noted capability (closures, GValue in/out). */
static PyMethodDef methods[] = {
  /* keep: scans typelibs on disk (no introspection involved) */
  { "installed_versions", py_installed_versions, METH_NOARGS, NULL },
  /* keep: test-infra — pre-loads a .so so g_module_open("libfoo.so") hits cache */
  { "preload_shared_library", py_preload_shared_library, METH_VARARGS, NULL },
  /* keep: creates the GObject type with the Python GObjectMeta metaclass */
  { "init_gobject", py_init_gobject, METH_VARARGS, NULL },
  /* keep: bootstrap handshake — Python registers GObject.Object instance hooks
   * (__getattr__/__setattr__/_finish_construction) so C slots never import back */
  { "register_gobject_callbacks",
    (PyCFunction)(void (*) (void))pygi_register_gobject_callbacks,
    METH_VARARGS | METH_KEYWORDS,
    NULL },
  /* keep: test-infra — PyArg_ParseTuple oracle (release-build getargs_* equivalents) */
  { "getargs_b", py_getargs_b, METH_VARARGS, NULL },
  { "getargs_B", py_getargs_B, METH_VARARGS, NULL },
  { "getargs_h", py_getargs_h, METH_VARARGS, NULL },
  { "getargs_H", py_getargs_H, METH_VARARGS, NULL },
  { "getargs_i", py_getargs_i, METH_VARARGS, NULL },
  { "getargs_I", py_getargs_I, METH_VARARGS, NULL },
  { "getargs_l", py_getargs_l, METH_VARARGS, NULL },
  { "getargs_L", py_getargs_L, METH_VARARGS, NULL },
  { "getargs_n", py_getargs_n, METH_VARARGS, NULL },
  { "getargs_k", py_getargs_k, METH_VARARGS, NULL },
  { "getargs_K", py_getargs_K, METH_VARARGS, NULL },
  { "getargs_f", py_getargs_f, METH_VARARGS, NULL },
  { "getargs_d", py_getargs_d, METH_VARARGS, NULL },
  { "getargs_s", py_getargs_s, METH_VARARGS, NULL },
  /* keep: loads a typelib — bootstraps invoke */
  { "require_namespace", py_require_namespace, METH_VARARGS, NULL },
  /* keep: typelib metadata lookup — bootstraps invoke */
  { "namespace_find", py_namespace_find, METH_VARARGS, NULL },
  /* keep: typelib namespace listing */
  { "namespace_dir", py_namespace_dir, METH_VARARGS, NULL },
  { "namespace_is_registered", py_namespace_is_registered, METH_VARARGS, NULL },
  { "namespace_get_dependencies", py_namespace_get_dependencies, METH_VARARGS, NULL },
  { "namespace_get_immediate_dependencies", py_namespace_get_immediate_dependencies, METH_VARARGS, NULL },
  { "namespace_find_by_gtype", py_namespace_find_by_gtype, METH_VARARGS, NULL },
  { "namespace_get_typelib_path", py_namespace_get_typelib_path, METH_VARARGS, NULL },
  /* keep: repository gtype->info lookup */
  /* keep: fundamental-type unref lifecycle */
  { "instantiatable_unref", py_instantiatable_unref, METH_VARARGS, NULL },
  /* DROP: boxed constructor via invoke once invoke allocates boxed returns */
  { "record_new", py_record_new, METH_VARARGS, NULL },
  /* keep: creates a Python-subclassable GSource (special construction) */
  { "glib_event_source_new", py_glib_event_source_new, METH_VARARGS, NULL },
  /* keep: boxed field read marshalling primitive */
  { "record_field_get", py_record_field_get, METH_VARARGS, NULL },
  /* keep: boxed field write marshalling primitive */
  { "record_field_set", py_record_field_set, METH_VARARGS, NULL },
  /* keep: create a fundamental wrapper from a raw pointer (called from classbuild) */
  { "fundamental_from_pointer", py_fundamental_from_pointer, METH_VARARGS, NULL },
  /* keep: register Python-side hooks for the Fundamental C type (bootstrap) */
  { "fundamental_init_hooks", py_fundamental_init_hooks, METH_VARARGS, NULL },
  /* keep: anonymous-union storage sizing (memory primitive) */
  { "record_ensure_size", py_record_ensure_size, METH_VARARGS, NULL },
  /* keep: raw memory read for anonymous unions */
  { "record_memory_get", py_record_memory_get, METH_VARARGS, NULL },
  /* keep: raw memory write for anonymous unions */
  { "record_memory_set", py_record_memory_set, METH_VARARGS, NULL },
  /* DROP: g_boxed_copy via invoke */
  { "record_copy", py_record_copy, METH_VARARGS, NULL },
  /* keep: boxed identity helper (no introspection) */
  { "record_pointer_equal", py_record_pointer_equal, METH_VARARGS, NULL },
  /* keep: boxed pointer value for hashing (no introspection) */
  { "record_pointer_value", py_record_pointer_value, METH_VARARGS, NULL },
  { "record_install_field_descriptors", py_record_install_field_descriptors, METH_VARARGS, NULL },
  { "record_field_names", py_record_field_names, METH_VARARGS, NULL },
  /* keep: boxed GType registration */
  { "register_boxed_class", py_register_boxed_class, METH_VARARGS, NULL },
  /* keep: invoke instrumentation (debug) */
  { "reset_invoke_stats", py_reset_invoke_stats, METH_NOARGS, NULL },
  /* keep: invoke instrumentation (debug) */
  { "invoke_stats", py_invoke_stats, METH_NOARGS, NULL },
  /* keep: builds the invoke descriptor (core) */
  { "build_callable_descriptor", py_build_callable_descriptor, METH_VARARGS, NULL },
  /* keep: the invoke path (core) */
  { "invoke_callable_descriptor",
    (PyCFunction)(void (*) (void))py_invoke_callable_descriptor,
    METH_FASTCALL | METH_KEYWORDS,
    NULL },
  /* keep: cached synthetic callables for non-introspectable bridge APIs */
  { "synthetic_callable", py_synthetic_callable, METH_VARARGS, NULL },
  /* keep: reads typelib async (finish-func + callback position) metadata
           for ginext.aio AsyncCallable wrapping */
  { "callable_async_info", py_callable_async_info, METH_VARARGS, NULL },
  /* keep: class-struct method dispatch (special) */
  { "class_struct_wrapper", py_class_struct_wrapper, METH_VARARGS, NULL },
  /* keep: THE invoke-by-name fast path (core) */
  { "invoke", (PyCFunction)(void (*) (void))py_invoke_by_name, METH_FASTCALL, NULL },
  /* keep: GValue marshalling primitive (invoke depends on it) */
  { "gvalue_get_type", py_gvalue_get_type, METH_VARARGS, NULL },
  /* keep: GValue marshalling primitive */
  { "gvalue_get_gtype", py_gvalue_get_gtype, METH_VARARGS, NULL },
  /* keep: GValue marshalling primitive */
  { "gvalue_init_value", py_gvalue_init_value, METH_VARARGS, NULL },
  /* keep: GValue marshalling primitive */
  { "gvalue_unset_value", py_gvalue_unset_value, METH_VARARGS, NULL },
  /* keep: GValue marshalling primitive */
  { "gvalue_reset_value", py_gvalue_reset_value, METH_VARARGS, NULL },
  /* keep: GValue marshalling primitive */
  { "gvalue_get_value", py_gvalue_get_value, METH_VARARGS, NULL },
  /* keep: GValue marshalling primitive */
  { "gvalue_set_value", py_gvalue_set_value, METH_VARARGS, NULL },
  { "gvalue_array_get_nth_type", py_gvalue_array_get_nth_type, METH_VARARGS, NULL },
  /* keep: extension point for custom-fundamental GType converters */
  { "gvalue_set_to_py_fallback", py_gvalue_set_to_py_fallback, METH_VARARGS, NULL },
  { "gvalue_get_to_py_fallback", py_gvalue_get_to_py_fallback, METH_NOARGS, NULL },
  { "gvalue_set_from_py_converter", py_gvalue_set_from_py_converter, METH_VARARGS, NULL },
  { "gvalue_get_from_py_converter", py_gvalue_get_from_py_converter, METH_NOARGS, NULL },
  { "gvalue_set_data_int", py_gvalue_set_data_int, METH_VARARGS, NULL },
  { "gvalue_set_data_uint64", py_gvalue_set_data_uint64, METH_VARARGS, NULL },
  /* keep: allocates a zeroed GValue wrapper for a given GType */
  { "gvalue_new_for_gtype", py_gvalue_new_for_gtype, METH_VARARGS, NULL },
  { "gvalue_wrap_pointer", py_gvalue_wrap_pointer, METH_VARARGS, NULL },
  /* DROP-ish: GLib.strv_get_type exists, but GType.STRV is set at gobject.py
           module load where importing GLib is circular — defer that constant first */
  { "gstrv_get_type", py_gstrv_get_type, METH_VARARGS, NULL },
  /* keep: g_error_get_type is not introspected (special-cased boxed) — no invoke path */
  { "gerror_get_type", py_gerror_get_type, METH_VARARGS, NULL },
  /* keep: compat foreign cairo needs cairo-gobject type registration side effects */
  { "ensure_cairo_gobject_types", py_ensure_cairo_gobject_types, METH_VARARGS, NULL },
  /* keep: GType-system query — no introspected method */
  { "type_has_value_table", py_type_has_value_table, METH_VARARGS, NULL },
  /* keep: registers a new pointer GType */
  { "pointer_type_register_static", py_pointer_type_register_static, METH_VARARGS, NULL },
  /* keep: reads GParamSpec fields for introspection — no method */
  { "param_spec_info", py_param_spec_info, METH_VARARGS, NULL },
  /* keep: reads a pspec default value — no method */
  { "param_spec_default_value", py_param_spec_default_value, METH_VARARGS, NULL },
  /* keep: reads a pspec numeric range — no method */
  { "param_spec_numeric_info", py_param_spec_numeric_info, METH_VARARGS, NULL },
  /* keep: GObject.weak_ref(callback, *args) — registers a GWeakNotify */
  { "gobject_add_weak_notify", py_gobject_add_weak_notify, METH_VARARGS, NULL },
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
  if (PyType_Ready (&GinextDeclaredPropertyType) < 0)
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

  PyObject *method_descriptor_type = PyType_FromSpec (&GinextMethodDescriptor_spec);
  if (method_descriptor_type == NULL)
    {
      Py_DECREF (m);
      return NULL;
    }
  ginext_method_descriptor_type = (PyTypeObject *)method_descriptor_type;
  if (PyModule_AddObject (m, "MethodDescriptor", method_descriptor_type) < 0)
    {
      Py_DECREF (method_descriptor_type);
      Py_DECREF (m);
      return NULL;
    }

  PyObject *vfunc_wrapper_type = PyType_FromSpec (&GinextVFuncWrapper_spec);
  if (vfunc_wrapper_type == NULL)
    {
      Py_DECREF (m);
      return NULL;
    }
  ginext_vfunc_wrapper_type = (PyTypeObject *)vfunc_wrapper_type;
  if (PyModule_AddObject (m, "VFuncWrapper", vfunc_wrapper_type) < 0)
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
  if (PyModule_AddObject (m, "CallbackWrapper", reverse_callback_type) < 0)
    {
      Py_DECREF (reverse_callback_type);
      Py_DECREF (m);
      return NULL;
    }

  Py_INCREF (&GIMetaType);
  if (PyModule_AddObject (m, "GIMeta", (PyObject *)&GIMetaType) < 0)
    {
      Py_DECREF (&GIMetaType);
      Py_DECREF (m);
      return NULL;
    }
  Py_INCREF (&GinextDeclaredPropertyType);
  if (PyModule_AddObject (m, "DeclaredProperty", (PyObject *)&GinextDeclaredPropertyType) < 0)
    {
      Py_DECREF (&GinextDeclaredPropertyType);
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

  return m;
}
