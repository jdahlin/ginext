/* Copyright 2026 Johan Dahlin
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 */

/* GIR-driven `do_<vfunc>` overrides for Python-defined GObject subclasses.
 *
 * The parent class's GIObjectInfo tells us which vfunc names exist and where
 * their function-pointer fields live in the class struct. For each callable
 * `do_foo` declared directly on the Python subclass, we resolve GIR vfunc
 * `foo`, build a libffi callback using the callable signature from the class
 * struct field, and write the callback pointer into the new GType's vtable.
 */
#include "GObject/Object-vfunc.h"

#include <string.h>

#include <girepository/girepository.h>
#include <glib.h>

#include "GObject/Closure.h"
#include "GIRepository/BaseInfo.h"
#include "common.h"
#include "gimeta-helpers.h"

static GIObjectInfo *
object_info_from_python_class (PyObject *cls)
{
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "cls is not a type");
      return NULL;
    }
  PyObject *mro = ((PyTypeObject *)cls)->tp_mro;
  if (mro == NULL)
    {
      PyErr_SetString (PyExc_TypeError, "__mro__ is not initialized");
      return NULL;
    }
  if (!PyTuple_Check (mro))
    {
      PyErr_SetString (PyExc_TypeError, "__mro__ is not a tuple");
      return NULL;
    }
  Py_INCREF (mro);

  Py_ssize_t n = PyTuple_GET_SIZE (mro);
  for (Py_ssize_t i = 0; i < n; i++)
    {
      PyObject *base = PyTuple_GET_ITEM (mro, i);
      PyObject *gimeta = NULL;
      if (pygi_object_get_gimeta (base, &gimeta) < 0)
        {
          Py_DECREF (mro);
          return NULL;
        }
      if (gimeta == NULL)
        continue;

      PyObject *gi_info = NULL;
      if (pygi_gimeta_get_gi_info (gimeta, &gi_info) < 0)
        {
          Py_DECREF (gimeta);
          Py_DECREF (mro);
          return NULL;
        }
      Py_DECREF (gimeta);
      if (gi_info == NULL)
        continue;

      GIBaseInfo *info = gi_info_from_py (gi_info);
      Py_DECREF (gi_info);
      if (info != NULL)
        {
          Py_DECREF (mro);
          if (GI_IS_OBJECT_INFO (info))
            return (GIObjectInfo *)gi_base_info_ref (info);
          return NULL;
        }
      PyErr_Clear ();
    }

  Py_DECREF (mro);
  return NULL;
}

static int
interface_info_from_python_base (PyObject *base, GIInterfaceInfo **out)
{
  *out = NULL;

  PyObject *gimeta = NULL;
  if (pygi_object_get_gimeta (base, &gimeta) < 0)
    return -1;
  if (gimeta == NULL)
    return 0;

  PyObject *gi_info = NULL;
  if (pygi_gimeta_get_gi_info (gimeta, &gi_info) < 0)
    {
      Py_DECREF (gimeta);
      return -1;
    }
  Py_DECREF (gimeta);
  if (gi_info == NULL)
    return 0;

  GIBaseInfo *info = gi_info_from_py (gi_info);
  Py_DECREF (gi_info);
  if (info == NULL)
    {
      PyErr_Clear ();
      return 0;
    }
  if (!GI_IS_INTERFACE_INFO (info))
    return 0;

  *out = (GIInterfaceInfo *)gi_base_info_ref (info);
  return 1;
}

static GIVFuncInfo *
find_vfunc_in_hierarchy (GIObjectInfo *parent_info,
                         const char *vfunc_name,
                         GIBaseInfo **container_out)
{
  GIObjectInfo *cur = (GIObjectInfo *)gi_base_info_ref ((GIBaseInfo *)parent_info);
  while (cur != NULL)
    {
      GIVFuncInfo *vfunc = gi_object_info_find_vfunc (cur, vfunc_name);
      if (vfunc != NULL)
        {
          *container_out = (GIBaseInfo *)cur;
          return vfunc;
        }

      unsigned int n_ifaces = gi_object_info_get_n_interfaces (cur);
      for (unsigned int i = 0; i < n_ifaces; i++)
        {
          g_autoptr (GIInterfaceInfo) iface = gi_object_info_get_interface (cur, i);
          if (iface == NULL)
            continue;
          GIVFuncInfo *iface_vfunc = gi_interface_info_find_vfunc (iface, vfunc_name);
          if (iface_vfunc != NULL)
            {
              *container_out = gi_base_info_ref ((GIBaseInfo *)iface);
              gi_base_info_unref ((GIBaseInfo *)cur);
              return iface_vfunc;
            }
        }

      GIObjectInfo *parent = gi_object_info_get_parent (cur);
      gi_base_info_unref ((GIBaseInfo *)cur);
      cur = parent;
    }

  *container_out = NULL;
  return NULL;
}

static char *
snake_case_type_name (const char *type_name)
{
  if (type_name == NULL || *type_name == '\0')
    return NULL;

  GString *out = g_string_new (NULL);
  for (const char *p = type_name; *p != '\0'; p++)
    {
      gunichar ch = (gunichar)(guchar)*p;
      if (g_ascii_isupper ((gchar)ch))
        {
          if (out->len > 0)
            g_string_append_c (out, '_');
          g_string_append_c (out, (gchar)g_ascii_tolower ((gchar)ch));
        }
      else
        {
          g_string_append_c (out, (gchar)ch);
        }
    }
  return g_string_free (out, FALSE);
}

static gboolean
match_explicit_vfunc_name (GIBaseInfo *container_info,
                           GIVFuncInfo *vfunc_info,
                           const char *python_name)
{
  const char *container_name = gi_base_info_get_name (container_info);
  const char *vfunc_name = gi_base_info_get_name ((GIBaseInfo *)vfunc_info);
  if (container_name == NULL || vfunc_name == NULL || python_name == NULL)
    return FALSE;

  g_autofree char *snake = snake_case_type_name (container_name);
  if (snake == NULL)
    return FALSE;

  g_autofree char *expected = g_strconcat ("do_", snake, "_", vfunc_name, NULL);
  return g_strcmp0 (expected, python_name) == 0;
}

static GIObjectInfo *
gi_object_info_get_parent_ref (GIObjectInfo *info)
{
  GIObjectInfo *parent = gi_object_info_get_parent (info);
  return parent != NULL ? (GIObjectInfo *)gi_base_info_ref ((GIBaseInfo *)parent) : NULL;
}

static PyObject *
python_class_mro (PyObject *cls)
{
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "cls is not a type");
      return NULL;
    }
  PyObject *mro = ((PyTypeObject *)cls)->tp_mro;
  if (mro == NULL)
    {
      PyErr_SetString (PyExc_TypeError, "__mro__ is not initialized");
      return NULL;
    }
  if (!PyTuple_Check (mro))
    {
      PyErr_SetString (PyExc_TypeError, "__mro__ is not a tuple");
      return NULL;
    }
  return Py_NewRef (mro);
}

static GIVFuncInfo *
find_explicit_vfunc_for_python_name (PyObject *cls,
                                     const char *python_name,
                                     GIBaseInfo **container_out)
{
  *container_out = NULL;

  Py_AUTO_DECREF PyObject *mro = python_class_mro (cls);
  if (mro == NULL)
    return NULL;

  Py_ssize_t n = PyTuple_GET_SIZE (mro);
  for (Py_ssize_t i = 1; i < n; i++)
    {
      PyObject *base_cls = PyTuple_GET_ITEM (mro, i);
      PyObject *gimeta = NULL;
      if (pygi_object_get_gimeta (base_cls, &gimeta) < 0)
        return NULL;
      if (gimeta == NULL)
        continue;

      PyObject *gi_info = NULL;
      if (pygi_gimeta_get_gi_info (gimeta, &gi_info) < 0)
        {
          Py_DECREF (gimeta);
          return NULL;
        }
      Py_DECREF (gimeta);
      if (gi_info == NULL)
        continue;

      GIBaseInfo *info = gi_info_from_py (gi_info);
      Py_DECREF (gi_info);
      if (info == NULL)
        {
          PyErr_Clear ();
          continue;
        }

      if (GI_IS_OBJECT_INFO (info))
        {
          g_autoptr (GIObjectInfo) obj = (GIObjectInfo *)gi_base_info_ref (info);
          unsigned int n_vfuncs = gi_object_info_get_n_vfuncs (obj);
          for (unsigned int vi = 0; vi < n_vfuncs; vi++)
            {
              g_autoptr (GIVFuncInfo) vfunc = gi_object_info_get_vfunc (obj, vi);
              if (vfunc != NULL
                  && match_explicit_vfunc_name ((GIBaseInfo *)obj, vfunc, python_name))
                {
                  *container_out = gi_base_info_ref ((GIBaseInfo *)obj);
                  return (GIVFuncInfo *)gi_base_info_ref ((GIBaseInfo *)vfunc);
                }
            }
        }

      g_autoptr (GIInterfaceInfo) iface = NULL;
      int interface_result = interface_info_from_python_base (base_cls, &iface);
      if (interface_result < 0)
        return NULL;
      if (interface_result > 0)
        {
          unsigned int n_vfuncs = gi_interface_info_get_n_vfuncs (iface);
          for (unsigned int vi = 0; vi < n_vfuncs; vi++)
            {
              g_autoptr (GIVFuncInfo) vfunc = gi_interface_info_get_vfunc (iface, vi);
              if (vfunc != NULL
                  && match_explicit_vfunc_name ((GIBaseInfo *)iface, vfunc, python_name))
                {
                  *container_out = gi_base_info_ref ((GIBaseInfo *)iface);
                  return (GIVFuncInfo *)gi_base_info_ref ((GIBaseInfo *)vfunc);
                }
            }
        }
    }

  return NULL;
}

static GIVFuncInfo *
find_vfunc_in_python_interface_bases (PyObject *cls,
                                      const char *vfunc_name,
                                      GIBaseInfo **container_out)
{
  *container_out = NULL;

  Py_AUTO_DECREF PyObject *mro = python_class_mro (cls);
  if (mro == NULL)
    return NULL;

  Py_ssize_t n = PyTuple_GET_SIZE (mro);
  for (Py_ssize_t i = 1; i < n; i++)
    {
      PyObject *base_cls = PyTuple_GET_ITEM (mro, i);
      g_autoptr (GIInterfaceInfo) iface = NULL;
      int interface_result = interface_info_from_python_base (base_cls, &iface);
      if (interface_result < 0)
        return NULL;
      if (interface_result <= 0)
        continue;

      GIVFuncInfo *vfunc = gi_interface_info_find_vfunc (iface, vfunc_name);
      if (vfunc != NULL)
        {
          *container_out = gi_base_info_ref ((GIBaseInfo *)iface);
          return vfunc;
        }
    }

  return NULL;
}

static gboolean
has_conflicting_vfunc_in_hierarchy (GIObjectInfo *parent_info,
                                    GIVFuncInfo *matched_vfunc,
                                    GIBaseInfo *matched_container)
{
  const char *matched_name = gi_base_info_get_name ((GIBaseInfo *)matched_vfunc);
  if (matched_name == NULL)
    return FALSE;

  GIObjectInfo *cur = (GIObjectInfo *)gi_base_info_ref ((GIBaseInfo *)parent_info);
  while (cur != NULL)
    {
      GIVFuncInfo *cur_vfunc = gi_object_info_find_vfunc (cur, matched_name);
      if (cur_vfunc != NULL)
        {
          gboolean conflict
              = gi_base_info_equal ((GIBaseInfo *)cur_vfunc, (GIBaseInfo *)matched_vfunc) == FALSE
                || gi_base_info_equal ((GIBaseInfo *)cur, matched_container) == FALSE;
          gi_base_info_unref ((GIBaseInfo *)cur_vfunc);
          if (conflict)
            return TRUE;
        }

      unsigned int n_ifaces = gi_object_info_get_n_interfaces (cur);
      for (unsigned int i = 0; i < n_ifaces; i++)
        {
          g_autoptr (GIInterfaceInfo) iface = gi_object_info_get_interface (cur, i);
          if (iface == NULL)
            continue;
          GIVFuncInfo *iface_vfunc = gi_interface_info_find_vfunc (iface, matched_name);
          if (iface_vfunc != NULL)
            {
              gboolean same_vfunc
                  = gi_base_info_equal ((GIBaseInfo *)iface_vfunc, (GIBaseInfo *)matched_vfunc);
              gboolean same_container = gi_base_info_equal ((GIBaseInfo *)iface, matched_container);
              gi_base_info_unref ((GIBaseInfo *)iface_vfunc);
              if (!same_vfunc || !same_container)
                return TRUE;
            }
        }

      GIObjectInfo *next = gi_object_info_get_parent_ref (cur);
      gi_base_info_unref ((GIBaseInfo *)cur);
      cur = next;
    }

  return FALSE;
}

static int
validate_vfunc_overrides (PyObject *cls, GIObjectInfo *parent_info)
{
  PyObject *dict = ((PyTypeObject *)cls)->tp_dict;
  if (dict == NULL)
    return 0;

  PyObject *key = NULL;
  PyObject *value = NULL;
  Py_ssize_t pos = 0;
  while (PyDict_Next (dict, &pos, &key, &value))
    {
      if (!PyUnicode_Check (key) || !PyCallable_Check (value))
        continue;

      Py_ssize_t key_len = 0;
      const char *key_str = PyUnicode_AsUTF8AndSize (key, &key_len);
      if (key_str == NULL)
        {
          PyErr_Clear ();
          continue;
        }
      if (key_len <= 3 || strncmp (key_str, "do_", 3) != 0)
        continue;

      GIBaseInfo *container = NULL;
      g_autoptr (GIVFuncInfo) vfunc_info
          = find_explicit_vfunc_for_python_name (cls, key_str, &container);
      gboolean explicit_match = vfunc_info != NULL;
      if (vfunc_info == NULL)
        {
          const char *vfunc_name = key_str + 3;
          if (parent_info != NULL)
            vfunc_info = find_vfunc_in_hierarchy (parent_info, vfunc_name, &container);
          if (vfunc_info == NULL)
            vfunc_info = find_vfunc_in_python_interface_bases (cls, vfunc_name, &container);
        }
      if (vfunc_info == NULL)
        continue;

      if (parent_info != NULL && !explicit_match
          && has_conflicting_vfunc_in_hierarchy (parent_info, vfunc_info, container))
        {
          PyErr_Format (PyExc_TypeError,
                        "Method %s() on class %s is ambiguous with methods in base classes",
                        key_str,
                        ((PyTypeObject *)cls)->tp_name);
          if (container != NULL)
            gi_base_info_unref (container);
          return -1;
        }

      if (container != NULL)
        gi_base_info_unref (container);
    }

  return 0;
}

static int
install_one_vfunc (GType new_gt,
                   GIBaseInfo *container_info,
                   GIVFuncInfo *vfunc_info,
                   PyObject *py_function)
{
  const char *vfunc_name = gi_base_info_get_name ((GIBaseInfo *)vfunc_info);
  gpointer implementor_class = g_type_class_ref (new_gt);
  if (implementor_class == NULL)
    {
      PyErr_Format (PyExc_RuntimeError, "g_type_class_ref failed for vfunc '%s'", vfunc_name);
      return -1;
    }

  gpointer implementor_vtable = NULL;
  GIStructInfo *struct_info = NULL;
  if (GI_IS_INTERFACE_INFO (container_info))
    {
      GType iface_gt = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)container_info);
      implementor_vtable = g_type_interface_peek (implementor_class, iface_gt);
      if (implementor_vtable == NULL)
        {
          g_type_class_unref (implementor_class);
          return 0;
        }
      struct_info = gi_interface_info_get_iface_struct ((GIInterfaceInfo *)container_info);
    }
  else
    {
      implementor_vtable = implementor_class;
      struct_info = gi_object_info_get_class_struct ((GIObjectInfo *)container_info);
    }

  if (struct_info == NULL)
    {
      g_type_class_unref (implementor_class);
      PyErr_Format (PyExc_RuntimeError,
                    "vfunc '%s': container has no class/iface struct",
                    vfunc_name);
      return -1;
    }

  g_autoptr (GIFieldInfo) field_info = gi_struct_info_find_field (struct_info, vfunc_name);
  gi_base_info_unref ((GIBaseInfo *)struct_info);
  if (field_info == NULL)
    {
      g_type_class_unref (implementor_class);
      return 0;
    }

  g_autoptr (GITypeInfo) field_ti = gi_field_info_get_type_info (field_info);
  if (field_ti == NULL || gi_type_info_get_tag (field_ti) != GI_TYPE_TAG_INTERFACE)
    {
      g_type_class_unref (implementor_class);
      return 0;
    }

  g_autoptr (GIBaseInfo) field_iface = gi_type_info_get_interface (field_ti);
  if (field_iface == NULL || !GI_IS_CALLABLE_INFO (field_iface))
    {
      g_type_class_unref (implementor_class);
      return 0;
    }

  GIArgument out = { 0 };
  PyGIArgCleanup cleanup = { 0 };
  if (pygi_vfunc_closure_new (py_function, field_iface, &out, &cleanup) != 0)
    {
      g_type_class_unref (implementor_class);
      return -1;
    }

  size_t offset = gi_field_info_get_offset (field_info);
  *((gpointer *)((char *)implementor_vtable + offset)) = out.v_pointer;

  /* Keep the class referenced so the patched vtable has class lifetime. */
  return 0;
}

int
ginext_gobject_validate_vfunc_overrides (PyObject *cls, PyObject *parent_cls)
{
  if (!PyType_Check (cls))
    return 0;

  g_autoptr (GIObjectInfo) parent_info = object_info_from_python_class (parent_cls);
  if (parent_info == NULL && PyErr_Occurred ())
    return -1;

  return validate_vfunc_overrides (cls, parent_info);
}

int
ginext_gobject_install_vfunc_overrides (PyObject *cls, GType new_gt, PyObject *parent_cls)
{
  if (!PyType_Check (cls))
    return 0;

  g_autoptr (GIObjectInfo) parent_info = object_info_from_python_class (parent_cls);
  if (parent_info == NULL && PyErr_Occurred ())
    return -1;

  if (validate_vfunc_overrides (cls, parent_info) < 0)
    return -1;

  PyObject *dict = ((PyTypeObject *)cls)->tp_dict;
  if (dict == NULL)
    return 0;

  PyObject *key = NULL;
  PyObject *value = NULL;
  Py_ssize_t pos = 0;
  while (PyDict_Next (dict, &pos, &key, &value))
    {
      if (!PyUnicode_Check (key) || !PyCallable_Check (value))
        continue;

      Py_ssize_t key_len = 0;
      const char *key_str = PyUnicode_AsUTF8AndSize (key, &key_len);
      if (key_str == NULL)
        {
          PyErr_Clear ();
          continue;
        }
      if (key_len <= 3 || strncmp (key_str, "do_", 3) != 0)
        continue;

      GIBaseInfo *container = NULL;
      g_autoptr (GIVFuncInfo) vfunc_info
          = find_explicit_vfunc_for_python_name (cls, key_str, &container);
      if (vfunc_info == NULL)
        {
          const char *vfunc_name = key_str + 3;
          if (parent_info != NULL)
            vfunc_info = find_vfunc_in_hierarchy (parent_info, vfunc_name, &container);
          if (vfunc_info == NULL)
            vfunc_info = find_vfunc_in_python_interface_bases (cls, vfunc_name, &container);
        }
      if (vfunc_info == NULL)
        continue;

      int rc = install_one_vfunc (new_gt, container, vfunc_info, value);
      if (container != NULL)
        gi_base_info_unref (container);
      if (rc != 0)
        return -1;
    }

  return 0;
}
