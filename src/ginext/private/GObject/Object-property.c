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

#include "GObject/GIMeta.h"
#include "GObject/Object.h"
#include "GIRepository/BaseInfo.h"
#include "GIRepository/Info.h"
#include "GLib/List.h"
#include "GLib/HashTable.h"
#include "marshal/enum.h"
#include "marshal/gvalue.h"
#include "marshal/marshal.h"
#include "marshal/scalar.h"
#include "runtime/class-registry.h"
#include "runtime/module_funcs.h"
#include "gimeta-helpers.h"

#include <girepository/girepository.h>
#include <string.h>

#define info_from_capsule gi_info_from_py

static GHashTable *property_type_infos_by_key = NULL;

static char *
property_type_info_key (GType gtype, const char *name)
{
  return g_strdup_printf ("%" G_GUINT64_FORMAT ":%s", (guint64)gtype, name);
}

PyObject *
py_register_property_type_info (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  unsigned long long gtype_arg = 0;
  const char *name = NULL;
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "KsO", &gtype_arg, &name, &capsule))
    return NULL;

  if (pygi_register_property_type_info_for_gtype ((GType)gtype_arg, name, capsule) < 0)
    return NULL;
  Py_RETURN_NONE;
}

int
pygi_register_property_type_info_for_gtype (GType gtype, const char *name, PyObject *capsule)
{
  GIBaseInfo *base = gi_info_from_py (capsule);
  if (base == NULL)
    return -1;
  if (!GI_IS_PROPERTY_INFO (base))
    {
      PyErr_SetString (PyExc_TypeError, "expected GIPropertyInfo");
      return -1;
    }

  GITypeInfo *type_info = gi_property_info_get_type_info ((GIPropertyInfo *)base);
  if (type_info == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "property has no type info");
      return -1;
    }

  if (property_type_infos_by_key == NULL)
    property_type_infos_by_key = g_hash_table_new_full (g_str_hash,
                                                        g_str_equal,
                                                        g_free,
                                                        (GDestroyNotify)gi_base_info_unref);

  char *key = property_type_info_key (gtype, name);
  g_hash_table_replace (property_type_infos_by_key, key, type_info);
  return 0;
}

static GIBaseInfo *
object_info_for_gtype (GIRepository *repo, GType gtype)
{
  GIBaseInfo *info = repo != NULL ? gi_repository_find_by_gtype (repo, gtype) : NULL;
  if (info != NULL)
    return info;

  PyObject *cls = pygi_class_registry_get_pytype_for_gtype (gtype);
  if (cls == NULL)
    return NULL;

  PyObject *gimeta = NULL;
  if (pygi_object_get_gimeta (cls, &gimeta) < 0 || gimeta == NULL)
    {
      Py_XDECREF (gimeta);
      return NULL;
    }

  PyObject *gi_info_obj = NULL;
  if (pygi_gimeta_get_gi_info (gimeta, &gi_info_obj) < 0)
    {
      Py_DECREF (gimeta);
      return NULL;
    }
  Py_DECREF (gimeta);
  if (gi_info_obj == NULL)
    return NULL;

  info = gi_info_from_py (gi_info_obj);
  Py_DECREF (gi_info_obj);
  if (info == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  return gi_base_info_ref (info);
}

static GITypeInfo *
property_type_info_for_gobject_property (GObject *source, const char *name)
{
  GIRepository *repo = pygi_shared_repository ();

  for (GType gtype = G_OBJECT_TYPE (source); gtype != G_TYPE_INVALID && gtype != G_TYPE_NONE;
       gtype = g_type_parent (gtype))
    {
      if (property_type_infos_by_key != NULL)
        {
          g_autofree char *key = property_type_info_key (gtype, name);
          GITypeInfo *registered = g_hash_table_lookup (property_type_infos_by_key, key);
          if (registered != NULL)
            return (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)registered);
        }

      g_autoptr (GIBaseInfo) info = object_info_for_gtype (repo, gtype);
      if (info == NULL || !GI_IS_OBJECT_INFO (info))
        continue;

      int n_properties = gi_object_info_get_n_properties ((GIObjectInfo *)info);
      for (int i = 0; i < n_properties; i++)
        {
          g_autoptr (GIPropertyInfo) prop = gi_object_info_get_property ((GIObjectInfo *)info, i);
          if (prop == NULL)
            continue;
          const char *prop_name = gi_base_info_get_name ((GIBaseInfo *)prop);
          if (g_strcmp0 (prop_name, name) == 0)
            return gi_property_info_get_type_info (prop);
        }
    }

  return NULL;
}

PyObject *
pygi_gobject_get_property_by_name (PyObject *source_arg, const char *name)
{
  GObject *source = pygi_gobject_get (source_arg);
  if (source == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          if (PyLong_Check (source_arg))
            source = (GObject *)PyLong_AsVoidPtr (source_arg);
        }
      if (PyErr_Occurred ())
        return NULL;
    }
  if (source == NULL || !G_IS_OBJECT (source))
    {
      PyErr_SetString (PyExc_TypeError, "source is not a GObject");
      return NULL;
    }
  GParamSpec *pspec = g_object_class_find_property (G_OBJECT_GET_CLASS (source), name);
  if (pspec == NULL)
    {
      PyErr_Format (PyExc_AttributeError,
                    "%s has no property %s",
                    G_OBJECT_TYPE_NAME (source),
                    name);
      return NULL;
    }
  GValue value = G_VALUE_INIT;
  g_value_init (&value, pspec->value_type);
  g_object_get_property (source, name, &value);
  if (G_IS_PARAM_SPEC_UNICHAR (pspec))
    {
      guint codepoint = g_value_get_uint (&value);
      g_value_unset (&value);
      if (codepoint == 0)
        return PyUnicode_FromString ("");
      return PyUnicode_FromOrdinal ((int)codepoint);
    }
  if (pspec->value_type == G_TYPE_POINTER)
    {
      g_autoptr (GITypeInfo) type_info = property_type_info_for_gobject_property (source, name);
      if (type_info != NULL)
        {
          PyGIType pygi_type = { 0 };
          if (pygi_type_from_gi (type_info, &pygi_type) == 0
              && (pygi_type.kind == PYGI_TYPE_GLIST || pygi_type.kind == PYGI_TYPE_GSLIST))
            {
              GIArgument list_arg = { .v_pointer = g_value_get_pointer (&value) };
              PyObject *list_py = pygi_argument_to_py_transfer (NULL,
                                                                type_info,
                                                                &list_arg,
                                                                GI_TRANSFER_NOTHING);
              g_value_unset (&value);
              return list_py;
            }
        }
    }
  if (g_type_is_a (pspec->value_type, G_TYPE_HASH_TABLE))
    {
      if (g_value_get_boxed (&value) == NULL)
        {
          g_value_unset (&value);
          Py_RETURN_NONE;
        }
      g_autoptr (GITypeInfo) type_info = property_type_info_for_gobject_property (source, name);
      if (type_info == NULL || gi_type_info_get_tag (type_info) != GI_TYPE_TAG_GHASH)
        {
          g_value_unset (&value);
          PyErr_Format (PyExc_NotImplementedError,
                        "%s.%s GHashTable property metadata is unavailable",
                        G_OBJECT_TYPE_NAME (source),
                        name);
          return NULL;
        }
      GIArgument hash_arg = { .v_pointer = g_value_get_boxed (&value) };
      PyObject *dict = pygi_ghash_to_py (NULL, type_info, &hash_arg, GI_TRANSFER_NOTHING);
      g_value_unset (&value);
      return dict;
    }
  PyObject *py_value = pygi_gvalue_value_to_py (&value);
  g_value_unset (&value);
  return py_value;
}

PyObject *
py_object_get_property_by_name (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *source_arg;
  const char *name;
  if (!PyArg_ParseTuple (args, "Os", &source_arg, &name))
    return NULL;
  return pygi_gobject_get_property_by_name (source_arg, name);
}

int
pygi_gobject_set_property_on_object (GObject *source, const char *name, PyObject *py_value)
{
  GParamSpec *pspec = g_object_class_find_property (G_OBJECT_GET_CLASS (source), name);
  if (pspec == NULL)
    {
      PyErr_Format (PyExc_AttributeError,
                    "%s has no property %s",
                    G_OBJECT_TYPE_NAME (source),
                    name);
      return -1;
    }

  GValue value = G_VALUE_INIT;
  if (G_IS_PARAM_SPEC_UNICHAR (pspec))
    {
      GIArgument arg = { 0 };
      if (pygi_unichar_from_py (py_value, &arg) != 0)
        return -1;
      g_value_init (&value, pspec->value_type);
      g_value_set_uint (&value, arg.v_uint32);
      g_object_set_property (source, name, &value);
      g_value_unset (&value);
      return 0;
    }
  if (pspec->value_type == G_TYPE_POINTER)
    {
      g_autoptr (GITypeInfo) type_info = property_type_info_for_gobject_property (source, name);
      if (type_info != NULL)
        {
          PyGIType pygi_type = { 0 };
          if (pygi_type_from_gi (type_info, &pygi_type) == 0)
            {
              if (pygi_type.kind == PYGI_TYPE_GLIST || pygi_type.kind == PYGI_TYPE_GSLIST)
                {
                  GIArgument list_arg = { 0 };
                  PyGIArgCleanup cleanup = { 0 };
                  int rc = pygi_type.kind == PYGI_TYPE_GLIST
                               ? pygi_glist_from_py (py_value,
                                                     type_info,
                                                     GI_TRANSFER_NOTHING,
                                                     &list_arg,
                                                     &cleanup)
                               : pygi_slist_from_py (py_value,
                                                     type_info,
                                                     GI_TRANSFER_NOTHING,
                                                     &list_arg,
                                                     &cleanup);
                  if (rc != 0)
                    return -1;
                  g_value_init (&value, pspec->value_type);
                  g_value_set_pointer (&value, list_arg.v_pointer);
                  g_object_set_property (source, name, &value);
                  pygi_arg_cleanup_clear (&cleanup);
                  g_value_unset (&value);
                  return 0;
                }
            }
        }
    }
  if (g_type_is_a (pspec->value_type, G_TYPE_HASH_TABLE))
    {
      g_autoptr (GITypeInfo) type_info = property_type_info_for_gobject_property (source, name);
      if (type_info == NULL || gi_type_info_get_tag (type_info) != GI_TYPE_TAG_GHASH)
        {
          PyErr_Format (PyExc_NotImplementedError,
                        "%s.%s GHashTable property metadata is unavailable",
                        G_OBJECT_TYPE_NAME (source),
                        name);
          return -1;
        }
      GIArgument hash_arg = { 0 };
      PyGIArgCleanup cleanup = { 0 };
      if (pygi_ghash_from_py (py_value, type_info, GI_TRANSFER_NOTHING, &hash_arg, &cleanup) != 0)
        return -1;
      g_value_init (&value, pspec->value_type);
      g_value_set_boxed (&value, hash_arg.v_pointer);
      g_object_set_property (source, name, &value);
      pygi_arg_cleanup_clear (&cleanup);
      g_value_unset (&value);
      return 0;
    }
  if (pygi_py_to_gvalue_targeted (pspec->value_type, py_value, &value, "object property") != 0)
    {
      g_value_unset (&value);
      return -1;
    }
  g_object_set_property (source, name, &value);
  g_value_unset (&value);
  return 0;
}

PyObject *
pygi_gobject_set_property_by_name (PyObject *source_arg, const char *name, PyObject *py_value)
{
  GObject *source = pygi_gobject_get (source_arg);
  if (source == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          if (PyLong_Check (source_arg))
            source = (GObject *)PyLong_AsVoidPtr (source_arg);
        }
      if (PyErr_Occurred ())
        return NULL;
    }
  if (source == NULL || !G_IS_OBJECT (source))
    {
      PyErr_SetString (PyExc_TypeError, "source is not a GObject");
      return NULL;
    }
  if (pygi_gobject_set_property_on_object (source, name, py_value) != 0)
    return NULL;
  Py_RETURN_NONE;
}

PyObject *
py_object_set_property_by_name (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *source_arg;
  const char *name;
  PyObject *py_value;
  if (!PyArg_ParseTuple (args, "OsO", &source_arg, &name, &py_value))
    return NULL;
  return pygi_gobject_set_property_by_name (source_arg, name, py_value);
}

static void
set_shim_not_implemented (const char *message)
{
  PyErr_SetString (PyExc_NotImplementedError, message);
}

PyObject *
pygi_gobject_new (PyObject *type, GObject *object, int owned)
{
  (void)type;
  (void)object;
  (void)owned;
  set_shim_not_implemented (
      "TODO ginext: legacy GObject wrapper construction is outside the current invoke slice");
  return NULL;
}
