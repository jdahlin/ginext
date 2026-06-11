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

#include "GLib/Array.h"
#include "GLib/Error.h"
#include "GLib/HashTable.h"
#include "GLib/List.h"
#include "GLib/Variant.h"
#include "GObject/Boxed.h"
#include "GObject/Closure.h"
#include "GObject/Object.h"
#include "GObject/Object-class.h"
#include "GObject/Object-info.h"
#include "GIRepository/BaseInfo.h"
#include "GIRepository/Info.h"
#include "GObject/ParamSpec.h"
#include "cairo/foreign.h"
#include "marshal/container-element.h"
#include "marshal/enum.h"
#include "marshal/marshal.h"
#include "marshal/gvalue.h"
#include "GObject/Value.h"
#include "marshal/scalar.h"
#include "marshal/string.h"
#include "invoke/ffi/invoke.h"
#include "runtime/class-registry.h"
#include "runtime/callable.h"
#include "runtime/module_funcs.h"
#include "runtime/type-info.h"

#include <cairo-gobject.h>
#include "gimeta-helpers.h"

#include <ffi.h>
#include <girepository/girepository.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

PyTypeObject *pygi_gboxed_base_type = NULL;
PyTypeObject *pygi_gobject_type = NULL;

static PyObject *boxed_classes_by_gtype = NULL;
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
  if (PyObject_GetOptionalAttrString (cls, "gimeta", &gimeta) < 0 || gimeta == NULL)
    {
      Py_XDECREF (gimeta);
      return NULL;
    }

  PyObject *gi_info_obj = NULL;
  if (PyObject_GetOptionalAttrString (gimeta, "gi_info", &gi_info_obj) < 0)
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

static PyObject *
profile_name_from_object (PyObject *obj)
{
  PyObject *profile = PyObject_GetAttrString (obj, "_profile");
  if (profile == NULL)
    {
      PyErr_Clear ();
      PyObject *type = (PyObject *)Py_TYPE (obj);
      PyObject *gimeta = PyObject_GetAttrString (type, "gimeta");
      if (gimeta == NULL)
        {
          /* obj is a type object (e.g. a record/boxed class); look at its own gimeta */
          PyErr_Clear ();
          gimeta = PyObject_GetAttrString (obj, "gimeta");
        }
      if (gimeta != NULL)
        {
          profile = PyObject_GetAttrString (gimeta, "profile");
          Py_DECREF (gimeta);
        }
      if (profile == NULL)
        PyErr_Clear ();
    }
  if (profile == NULL)
    return PyUnicode_FromString ("native");
  PyObject *name = PyObject_GetAttrString (profile, "name");
  Py_DECREF (profile);
  if (name == NULL)
    {
      PyErr_Clear ();
      return PyUnicode_FromString ("native");
    }
  return name;
}

static PyObject *
profile_name_from_context (void)
{
  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    return NULL;
  return profile_name_from_object (context);
}

static PyObject *
boxed_registry_key (GType gtype, PyObject *profile_name)
{
  PyObject *gtype_obj = PyLong_FromUnsignedLongLong ((unsigned long long)gtype);
  if (gtype_obj == NULL)
    return NULL;
  PyObject *key = PyTuple_Pack (2, profile_name, gtype_obj);
  Py_DECREF (gtype_obj);
  return key;
}

typedef struct
{
  GSource source;
  PyObject *py_wrapper;
} PyGIEventSource;

PyObject *
py_gvalue_get_type (PyObject *m, PyObject *args)
{
  (void)m;
  if (!PyArg_ParseTuple (args, ""))
    return NULL;
  return PyLong_FromUnsignedLongLong ((unsigned long long)g_value_get_type ());
}

PyObject *
py_gvalue_get_gtype (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *wrapper;
  if (!PyArg_ParseTuple (args, "O", &wrapper))
    return NULL;
  GValue *value = NULL;
  if (!pygi_gvalue_wrapper_get (wrapper, &value))
    {
      PyErr_SetString (PyExc_TypeError, "expected a GObject.Value wrapper");
      return NULL;
    }
  return PyLong_FromUnsignedLongLong ((unsigned long long)G_VALUE_TYPE (value));
}

PyObject *
py_gvalue_init_value (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *wrapper;
  PyObject *gtype_obj;
  if (!PyArg_ParseTuple (args, "OO", &wrapper, &gtype_obj))
    return NULL;
  GValue *value = NULL;
  if (!pygi_gvalue_wrapper_get (wrapper, &value))
    {
      PyErr_SetString (PyExc_TypeError, "expected a GObject.Value wrapper");
      return NULL;
    }

  GType gtype = 0;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  if (gtype == 0 || !G_TYPE_IS_VALUE_TYPE (gtype))
    {
      PyErr_SetString (PyExc_ValueError, "Invalid GType");
      return NULL;
    }

  if (G_VALUE_TYPE (value) != 0)
    g_value_unset (value);
  g_value_init (value, gtype);
  Py_RETURN_NONE;
}

PyObject *
py_gvalue_unset_value (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *wrapper;
  if (!PyArg_ParseTuple (args, "O", &wrapper))
    return NULL;
  GValue *value = NULL;
  if (!pygi_gvalue_wrapper_get (wrapper, &value))
    {
      PyErr_SetString (PyExc_TypeError, "expected a GObject.Value wrapper");
      return NULL;
    }
  if (G_VALUE_TYPE (value) != 0)
    g_value_unset (value);
  Py_RETURN_NONE;
}

PyObject *
py_gvalue_reset_value (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *wrapper;
  if (!PyArg_ParseTuple (args, "O", &wrapper))
    return NULL;
  GValue *value = NULL;
  if (!pygi_gvalue_wrapper_get (wrapper, &value))
    {
      PyErr_SetString (PyExc_TypeError, "expected a GObject.Value wrapper");
      return NULL;
    }
  if (G_VALUE_TYPE (value) != 0)
    g_value_reset (value);
  Py_RETURN_NONE;
}

PyObject *
py_gvalue_get_value (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *wrapper;
  if (!PyArg_ParseTuple (args, "O", &wrapper))
    return NULL;
  GValue *value = NULL;
  if (!pygi_gvalue_wrapper_get (wrapper, &value))
    {
      PyErr_SetString (PyExc_TypeError, "expected a GObject.Value wrapper");
      return NULL;
    }
  return pygi_gvalue_value_to_py (value);
}

PyObject *
py_gvalue_set_value (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *wrapper;
  PyObject *py_value;
  if (!PyArg_ParseTuple (args, "OO", &wrapper, &py_value))
    return NULL;
  GValue *value = NULL;
  if (!pygi_gvalue_wrapper_get (wrapper, &value))
    {
      PyErr_SetString (PyExc_TypeError, "expected a GObject.Value wrapper");
      return NULL;
    }
  GType gtype = G_VALUE_TYPE (value);
  if (gtype == 0 || gtype == G_TYPE_INVALID)
    {
      PyErr_SetString (PyExc_TypeError, "GObject.Value needs to be initialized first");
      return NULL;
    }
  if (gtype == G_TYPE_STRING && PyBytes_Check (py_value))
    {
      PyErr_SetString (PyExc_TypeError, "string GValue expects str or None");
      return NULL;
    }
  GValue tmp = G_VALUE_INIT;
  if (pygi_py_to_gvalue_targeted (gtype, py_value, &tmp, "GObject.Value") != 0)
    return NULL;
  g_value_reset (value);
  g_value_copy (&tmp, value);
  g_value_unset (&tmp);
  Py_RETURN_NONE;
}

PyObject *
py_gvalue_set_to_py_fallback (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *callback;
  if (!PyArg_ParseTuple (args, "O", &callback))
    return NULL;
  if (callback == Py_None)
    callback = NULL;
  else if (!PyCallable_Check (callback))
    {
      PyErr_SetString (PyExc_TypeError, "expected callable or None");
      return NULL;
    }
  pygi_gvalue_set_to_py_fallback (callback);
  Py_RETURN_NONE;
}

PyObject *
py_gvalue_get_to_py_fallback (PyObject *m, PyObject *unused)
{
  (void)m;
  (void)unused;
  return pygi_gvalue_get_to_py_fallback ();
}

PyObject *
py_gvalue_set_from_py_converter (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *callback;
  if (!PyArg_ParseTuple (args, "O", &callback))
    return NULL;
  if (callback == Py_None)
    callback = NULL;
  else if (!PyCallable_Check (callback))
    {
      PyErr_SetString (PyExc_TypeError, "expected callable or None");
      return NULL;
    }
  pygi_gvalue_set_from_py_converter (callback);
  Py_RETURN_NONE;
}

PyObject *
py_gvalue_get_from_py_converter (PyObject *m, PyObject *unused)
{
  (void)m;
  (void)unused;
  return pygi_gvalue_get_from_py_converter ();
}

/* Write a primitive into one of a GValue's two data slots. Generic GValue field
 * access (no GType named): an overlay that knows a fundamental type's storage
 * (e.g. gst stores a fraction's numerator/denominator in data[0]/data[1].v_int)
 * uses this to fill a GValue its Python->GValue converter received. */
PyObject *
py_gvalue_set_data_int (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *ptr_obj;
  unsigned int index;
  int value;
  if (!PyArg_ParseTuple (args, "OIi", &ptr_obj, &index, &value))
    return NULL;
  if (index > 1)
    {
      PyErr_SetString (PyExc_IndexError, "GValue data index out of range");
      return NULL;
    }
  void *p = PyLong_AsVoidPtr (ptr_obj);
  if (p == NULL && PyErr_Occurred ())
    return NULL;
  ((GValue *)p)->data[index].v_int = value;
  Py_RETURN_NONE;
}

PyObject *
py_gvalue_set_data_uint64 (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *ptr_obj;
  unsigned int index;
  unsigned long long value;
  if (!PyArg_ParseTuple (args, "OIK", &ptr_obj, &index, &value))
    return NULL;
  if (index > 1)
    {
      PyErr_SetString (PyExc_IndexError, "GValue data index out of range");
      return NULL;
    }
  void *p = PyLong_AsVoidPtr (ptr_obj);
  if (p == NULL && PyErr_Occurred ())
    return NULL;
  ((GValue *)p)->data[index].v_uint64 = (guint64)value;
  Py_RETURN_NONE;
}

PyObject *
py_gvalue_new_for_gtype (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *gtype_obj;
  if (!PyArg_ParseTuple (args, "O", &gtype_obj))
    return NULL;
  GType gtype = 0;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  return pygi_gvalue_new_for_gtype (gtype);
}

PyObject *
py_gvalue_wrap_pointer (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *ptr_obj;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;
  void *value_ptr = PyLong_AsVoidPtr (ptr_obj);
  if (value_ptr == NULL && PyErr_Occurred ())
    return NULL;
  return pygi_gvalue_wrap_pointer ((GValue *)value_ptr);
}

PyObject *
py_gvalue_array_get_nth_type (PyObject *m, PyObject *args)
{
  (void)m;
  PyObject *wrapper;
  Py_ssize_t index;
  if (!PyArg_ParseTuple (args, "On", &wrapper, &index))
    return NULL;

  GValue *value = NULL;
  if (!pygi_gvalue_wrapper_get (wrapper, &value))
    {
      PyErr_SetString (PyExc_TypeError, "expected a GObject.Value wrapper");
      return NULL;
    }
  GType value_array_type = g_type_from_name ("GValueArray");
  if (value_array_type == G_TYPE_INVALID || G_VALUE_TYPE (value) != value_array_type)
    {
      PyErr_SetString (PyExc_TypeError, "expected GValueArray-compatible value");
      return NULL;
    }

  GValueArray *array = g_value_get_boxed (value);
  if (array == NULL)
    {
      PyErr_SetString (PyExc_TypeError, "expected GValueArray-compatible value");
      return NULL;
    }
  if (index < 0 || (guint)index >= array->n_values)
    {
      PyObject *index_obj = PyLong_FromSsize_t (index);
      if (index_obj == NULL)
        return NULL;
      PyErr_SetObject (PyExc_IndexError, index_obj);
      Py_DECREF (index_obj);
      return NULL;
    }

  GValue *item = &array->values[index];
  return PyLong_FromUnsignedLongLong ((unsigned long long)G_VALUE_TYPE (item));
}

PyObject *
py_gstrv_get_type (PyObject *m, PyObject *args)
{
  (void)m;
  if (!PyArg_ParseTuple (args, ""))
    return NULL;
  return PyLong_FromUnsignedLongLong ((unsigned long long)g_strv_get_type ());
}

PyObject *
py_gerror_get_type (PyObject *m, PyObject *args)
{
  (void)m;
  if (!PyArg_ParseTuple (args, ""))
    return NULL;
  return PyLong_FromUnsignedLongLong ((unsigned long long)G_TYPE_ERROR);
}

PyObject *
py_ensure_cairo_gobject_types (PyObject *m, PyObject *args)
{
  (void)m;
  if (!PyArg_ParseTuple (args, ""))
    return NULL;

  (void)cairo_gobject_context_get_type ();
  (void)cairo_gobject_device_get_type ();
  (void)cairo_gobject_matrix_get_type ();
  (void)cairo_gobject_pattern_get_type ();
  (void)cairo_gobject_surface_get_type ();
  (void)cairo_gobject_rectangle_get_type ();
  (void)cairo_gobject_scaled_font_get_type ();
  (void)cairo_gobject_font_face_get_type ();
  (void)cairo_gobject_font_options_get_type ();
  (void)cairo_gobject_rectangle_int_get_type ();
  (void)cairo_gobject_region_get_type ();
  (void)cairo_gobject_glyph_get_type ();
  (void)cairo_gobject_text_cluster_get_type ();
  (void)cairo_gobject_status_get_type ();
  (void)cairo_gobject_content_get_type ();
  (void)cairo_gobject_operator_get_type ();
  (void)cairo_gobject_antialias_get_type ();
  (void)cairo_gobject_fill_rule_get_type ();
  (void)cairo_gobject_line_cap_get_type ();
  (void)cairo_gobject_line_join_get_type ();
  (void)cairo_gobject_text_cluster_flags_get_type ();
  (void)cairo_gobject_font_slant_get_type ();
  (void)cairo_gobject_font_weight_get_type ();
  (void)cairo_gobject_subpixel_order_get_type ();
  (void)cairo_gobject_hint_style_get_type ();
  (void)cairo_gobject_hint_metrics_get_type ();
  (void)cairo_gobject_font_type_get_type ();
  (void)cairo_gobject_path_data_type_get_type ();
  (void)cairo_gobject_device_type_get_type ();
  (void)cairo_gobject_surface_type_get_type ();
  (void)cairo_gobject_format_get_type ();
  (void)cairo_gobject_pattern_type_get_type ();
  (void)cairo_gobject_extend_get_type ();
  (void)cairo_gobject_filter_get_type ();
  (void)cairo_gobject_region_overlap_get_type ();

  Py_RETURN_NONE;
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

#define info_from_capsule gi_info_from_py

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

PyObject *
pygi_error_to_py (GIArgument *arg, GITransfer transfer)
{
  GError *err = (GError *)arg->v_pointer;
  if (err == NULL)
    return Py_XNewRef (Py_None);

  PyObject *result = NULL;
  PyObject *module = PyImport_ImportModule ("ginext.errors");
  if (module != NULL)
    {
      PyObject *factory = PyObject_GetAttrString (module, "_exception_from_gerror");
      Py_DECREF (module);
      if (factory != NULL)
        {
          result = PyObject_CallFunction (factory,
                                          "kis",
                                          (unsigned long)err->domain,
                                          err->code,
                                          err->message ? err->message : "");
          Py_DECREF (factory);
        }
    }
  if (result != NULL)
    {
      if (transfer != GI_TRANSFER_NOTHING)
        g_error_free (err);
      return result;
    }
  PyErr_Clear ();

  PyObject *tuple = PyTuple_New (3);
  if (tuple == NULL)
    return NULL;
  PyTuple_SET_ITEM (tuple, 0, PyUnicode_FromString (g_quark_to_string (err->domain)));
  PyTuple_SET_ITEM (tuple, 1, PyLong_FromLong (err->code));
  PyTuple_SET_ITEM (tuple, 2, PyUnicode_FromString (err->message ? err->message : ""));
  if (transfer != GI_TRANSFER_NOTHING)
    g_error_free (err);
  return tuple;
}

static int
pygi_error_fields_from_tuple (PyObject *obj,
                              PyObject **domain_out,
                              PyObject **code_out,
                              PyObject **message_out)
{
  if (!PyTuple_Check (obj) || PyTuple_GET_SIZE (obj) != 3)
    return 0;

  *domain_out = Py_NewRef (PyTuple_GET_ITEM (obj, 0));
  *code_out = Py_NewRef (PyTuple_GET_ITEM (obj, 1));
  *message_out = Py_NewRef (PyTuple_GET_ITEM (obj, 2));
  return 1;
}

static int
pygi_error_fields_from_attrs (PyObject *obj,
                              PyObject **domain_out,
                              PyObject **code_out,
                              PyObject **message_out)
{
  PyObject *domain = PyObject_GetAttrString (obj, "domain");
  if (domain == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }

  PyObject *code = PyObject_GetAttrString (obj, "code");
  if (code == NULL)
    {
      Py_DECREF (domain);
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }

  PyObject *message = PyObject_GetAttrString (obj, "message");
  if (message == NULL)
    {
      Py_DECREF (domain);
      Py_DECREF (code);
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }

  *domain_out = domain;
  *code_out = code;
  *message_out = message;
  return 1;
}

int
pygi_error_from_py (PyObject *obj, GError **out_error)
{
  g_return_val_if_fail (out_error != NULL, -1);
  *out_error = NULL;

  if (obj == Py_None)
    return 1;

  PyObject *domain_obj = NULL;
  PyObject *code_obj = NULL;
  PyObject *message_obj = NULL;
  int rc = pygi_error_fields_from_tuple (obj, &domain_obj, &code_obj, &message_obj);
  if (rc == 0)
    rc = pygi_error_fields_from_attrs (obj, &domain_obj, &code_obj, &message_obj);
  if (rc <= 0)
    return rc;

  GQuark domain = 0;
  if (PyUnicode_Check (domain_obj))
    {
      const char *domain_str = PyUnicode_AsUTF8 (domain_obj);
      if (domain_str == NULL)
        {
          rc = -1;
          goto out;
        }
      domain = g_quark_from_string (domain_str);
    }
  else if (PyLong_Check (domain_obj))
    {
      unsigned long value = PyLong_AsUnsignedLong (domain_obj);
      if (value == (unsigned long)-1 && PyErr_Occurred ())
        {
          rc = -1;
          goto out;
        }
      domain = (GQuark)value;
    }
  else
    {
      PyErr_Format (PyExc_TypeError,
                    "GLib.Error domain must be str or int, not %.200s",
                    Py_TYPE (domain_obj)->tp_name);
      rc = -1;
      goto out;
    }

  long code = PyLong_AsLong (code_obj);
  if (code == -1 && PyErr_Occurred ())
    {
      rc = -1;
      goto out;
    }

  if (!PyUnicode_Check (message_obj))
    {
      PyErr_Format (PyExc_TypeError,
                    "GLib.Error message must be str, not %.200s",
                    Py_TYPE (message_obj)->tp_name);
      rc = -1;
      goto out;
    }
  const char *message = PyUnicode_AsUTF8 (message_obj);
  if (message == NULL)
    {
      rc = -1;
      goto out;
    }

  *out_error = g_error_new_literal (domain, (gint)code, message);
  rc = *out_error != NULL ? 1 : -1;

out:
  Py_XDECREF (domain_obj);
  Py_XDECREF (code_obj);
  Py_XDECREF (message_obj);
  return rc;
}

int
pygi_boxed_check (PyObject *obj)
{
  return obj != NULL && obj != Py_None && pygi_gboxed_base_type != NULL
         && PyObject_TypeCheck (obj, pygi_gboxed_base_type);
}

int
pygi_boxed_get (PyObject *obj, gpointer *out)
{
  if (obj == NULL || obj == Py_None)
    {
      if (out != NULL)
        *out = NULL;
      return 0;
    }
  if (!pygi_boxed_check (obj))
    {
      PyErr_Format (PyExc_TypeError,
                    "expected a GLib.Boxed wrapper, got %.200s",
                    Py_TYPE (obj)->tp_name);
      return -1;
    }
  if (out != NULL)
    *out = ((PyGIGLibBoxed *)obj)->boxed;
  return 0;
}

PyObject *
pygi_boxed_new (PyObject *cls, gpointer boxed, GType gtype, int transfer_full)
{
  if (cls == NULL || !PyType_Check (cls))
    {
      PyErr_SetString (PyExc_SystemError, "GLib.Boxed: cls is not a type");
      return NULL;
    }
  PyObject *self = ((PyTypeObject *)cls)->tp_alloc ((PyTypeObject *)cls, 0);
  if (self == NULL)
    return NULL;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  me->boxed = boxed;
  me->gtype = gtype;
  me->borrowed = transfer_full ? 0 : 1;
  me->heap_allocated = 0;
  me->size = 0;
  me->py_dict = NULL;
  me->parent = NULL;
  return self;
}

PyObject *
pygi_boxed_new_alias (PyObject *cls, gpointer boxed, GType gtype, PyObject *parent)
{
  PyObject *self = pygi_boxed_new (cls, boxed, gtype, 0);
  if (self == NULL)
    return NULL;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  me->borrowed = 1;
  me->parent = parent;
  Py_XINCREF (parent);
  return self;
}

int
pygi_boxed_promote_borrowed_alias (PyObject *obj)
{
  if (obj == NULL || !pygi_boxed_check (obj))
    return 0;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)obj;
  /* Only borrowed aliases into transient memory need promoting; an alias kept
   * alive by a parent already has a stable backing object. */
  if (!me->borrowed || me->parent != NULL || me->boxed == NULL)
    return 0;
  if (me->gtype == 0 || !G_TYPE_IS_BOXED (me->gtype))
    return 0;
  gpointer copy = g_boxed_copy (me->gtype, me->boxed);
  if (copy == NULL)
    return 0;
  me->boxed = copy;
  me->borrowed = 0;
  return 1;
}

PyObject *
pygi_boxed_new_heap (PyObject *cls, gpointer boxed, GType gtype, gsize size)
{
  if (cls == NULL || !PyType_Check (cls))
    {
      PyErr_SetString (PyExc_SystemError, "GLib.Boxed: cls is not a type");
      return NULL;
    }
  PyObject *self = ((PyTypeObject *)cls)->tp_alloc ((PyTypeObject *)cls, 0);
  if (self == NULL)
    return NULL;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  me->boxed = boxed;
  me->gtype = gtype;
  me->borrowed = 0;
  me->heap_allocated = 1;
  me->size = size;
  me->py_dict = NULL;
  me->parent = NULL;
  return self;
}

static PyObject *
GBoxedBase_new (PyTypeObject *type, PyObject *args, PyObject *kwds)
{
  (void)type;
  (void)args;
  (void)kwds;
  PyErr_SetString (PyExc_TypeError, "direct GLib.Boxed construction is unsupported");
  return NULL;
}

static void
GBoxedBase_dealloc (PyObject *self)
{
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  gpointer boxed = me->boxed;
  GType gtype = me->gtype;
  int borrowed = me->borrowed;
  int heap_allocated = me->heap_allocated;
  gsize size = me->size;
  PyObject *py_dict = me->py_dict;
  PyObject *parent = me->parent;

  me->boxed = NULL;
  me->gtype = 0;
  me->borrowed = 0;
  me->heap_allocated = 0;
  me->size = 0;
  me->py_dict = NULL;
  me->parent = NULL;

  if (boxed != NULL && !borrowed)
    {
      if (heap_allocated)
        {
          if (gtype == G_TYPE_VALUE && ((GValue *)boxed)->g_type != 0)
            g_value_unset ((GValue *)boxed);
          g_free (boxed);
        }
      else if (gtype == G_TYPE_VARIANT)
        g_variant_unref ((GVariant *)boxed);
      else if (gtype != 0)
        g_boxed_free (gtype, boxed);
      else if (size != 0)
        g_free (boxed);
    }
  Py_XDECREF (py_dict);
  Py_XDECREF (parent);
  Py_TYPE (self)->tp_free (self);
}

static PyObject *
GBoxedBase_repr (PyObject *self)
{
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  if (me->boxed == NULL)
    return PyUnicode_FromString ("<GLib.Boxed (detached)>");
  return PyUnicode_FromFormat ("<GLib.Boxed %s at %p>",
                               me->gtype != 0 ? g_type_name (me->gtype) : "?",
                               me->boxed);
}

static PyType_Slot PyGIGLibBoxed_slots[] = {
  { Py_tp_new, GBoxedBase_new },
  { Py_tp_dealloc, GBoxedBase_dealloc },
  { Py_tp_repr, GBoxedBase_repr },
  { 0, NULL },
};

PyType_Spec PyGIGLibBoxed_spec = {
  .name = "GLib.Boxed",
  .basicsize = sizeof (PyGIGLibBoxed),
  .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .slots = PyGIGLibBoxed_slots,
};

static gsize
record_info_size (GIBaseInfo *info)
{
  if (GI_IS_STRUCT_INFO (info))
    return gi_struct_info_get_size ((GIStructInfo *)info);
  if (GI_IS_UNION_INFO (info))
    return gi_union_info_get_size ((GIUnionInfo *)info);
  return 0;
}

static int
record_lookup_field (GIBaseInfo *info, const char *field_name, GIFieldInfo **field_out)
{
  if (info == NULL || field_name == NULL)
    return 0;
  int n_fields = gi_struct_or_union_n_fields (info);
  for (int fi = 0; fi < n_fields; fi++)
    {
      GIFieldInfo *field = gi_struct_or_union_get_field (info, (guint)fi);
      if (field == NULL)
        continue;
      const char *candidate = gi_base_info_get_name ((GIBaseInfo *)field);
      if (candidate != NULL && strcmp (candidate, field_name) == 0)
        {
          if (field_out != NULL)
            *field_out = field;
          else
            gi_base_info_unref ((GIBaseInfo *)field);
          return 1;
        }
      gi_base_info_unref ((GIBaseInfo *)field);
    }
  return 0;
}

static PyObject *
record_build_class_for_info (GIBaseInfo *info, PyObject *context)
{
  if (info == NULL)
    Py_RETURN_NONE;
  const char *namespace_name = gi_base_info_get_namespace (info);
  const char *name = gi_base_info_get_name (info);
  if (namespace_name == NULL || name == NULL)
    Py_RETURN_NONE;

  PyObject *ginext = PyImport_ImportModule ("ginext");
  if (ginext == NULL)
    return NULL;
  PyObject *resolver = PyObject_GetAttrString (ginext, "_class_from_namespace_profile");
  Py_DECREF (ginext);
  if (resolver == NULL)
    return NULL;
  PyObject *resolved_context = context != NULL ? context : pygi_namespace_context ();
  if (resolved_context == NULL)
    {
      Py_DECREF (resolver);
      return NULL;
    }
  PyObject *cls = PyObject_CallFunction (resolver, "Oss", resolved_context, namespace_name, name);
  Py_DECREF (resolver);
  return cls;
}

static PyObject *
boxed_shadow_get (PyObject *parent, const char *name)
{
  if (!pygi_boxed_check (parent) || name == NULL)
    Py_RETURN_NONE;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)parent;
  if (me->py_dict == NULL)
    Py_RETURN_NONE;
  PyObject *value = PyDict_GetItemString (me->py_dict, name);
  if (value == NULL)
    Py_RETURN_NONE;
  return Py_NewRef (value);
}

static int
boxed_shadow_set (PyObject *parent, const char *name, PyObject *value)
{
  if (!pygi_boxed_check (parent) || name == NULL)
    return -1;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)parent;
  if (me->py_dict == NULL)
    {
      me->py_dict = PyDict_New ();
      if (me->py_dict == NULL)
        return -1;
    }
  return PyDict_SetItemString (me->py_dict, name, value);
}

static PyObject *
union_interface_field_shadow_to_py (GITypeInfo *fti,
                                    char *base,
                                    size_t offset,
                                    PyObject *parent,
                                    const char *field_name)
{
  g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
  if (finfo == NULL || (!GI_IS_STRUCT_INFO (finfo) && !GI_IS_UNION_INFO (finfo)))
    return NULL;

  PyObject *cached = boxed_shadow_get (parent, field_name);
  if (cached == NULL)
    return NULL;
  if (cached != Py_None)
    return cached;
  Py_DECREF (cached);

  gsize size = record_info_size (finfo);
  if (size == 0)
    size = sizeof (void *);
  gpointer copy = g_malloc0 (size);
  if (copy == NULL)
    return PyErr_NoMemory ();
  memcpy (copy, base + offset, size);

  PyObject *cls = record_build_class_for_info (finfo, parent);
  if (cls == NULL)
    {
      g_free (copy);
      return NULL;
    }
  GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)finfo);
  PyObject *out = pygi_boxed_new_heap (cls, copy, gtype, size);
  Py_DECREF (cls);
  if (out == NULL)
    {
      g_free (copy);
      return NULL;
    }
  if (boxed_shadow_set (parent, field_name, out) != 0)
    {
      Py_DECREF (out);
      return NULL;
    }
  return out;
}

static PyObject *
array_field_to_py (GITypeInfo *fti, char *base, size_t offset, PyObject *parent)
{
  g_autoptr (GITypeInfo) inner_ti = gi_type_info_get_param_type (fti, 0);
  if (inner_ti == NULL)
    {
      PyErr_SetString (PyExc_NotImplementedError, "array field has no element type info");
      return NULL;
    }

  if (gi_type_info_get_array_type (fti) == GI_ARRAY_TYPE_ARRAY)
    {
      GArray *array = *(GArray **)((void *)(base + offset));
      if (array == NULL)
        Py_RETURN_NONE;

      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      if (itag == GI_TYPE_TAG_VOID || itag == GI_TYPE_TAG_UINT8)
        {
          PyObject *list = PyList_New ((Py_ssize_t)array->len);
          if (list == NULL)
            return NULL;
          for (guint i = 0; i < array->len; i++)
            {
              PyObject *item = PyLong_FromUnsignedLong ((guint8)array->data[i]);
              if (item == NULL)
                {
                  Py_DECREF (list);
                  return NULL;
                }
              PyList_SET_ITEM (list, (Py_ssize_t)i, item);
            }
          return list;
        }

      PyErr_SetString (PyExc_NotImplementedError, "unsupported GArray field element type");
      return NULL;
    }

  if (gi_type_info_get_array_type (fti) != GI_ARRAY_TYPE_C)
    {
      PyErr_SetString (PyExc_NotImplementedError, "unsupported array field type");
      return NULL;
    }

  if (gi_type_info_is_zero_terminated (fti))
    {
      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      if (itag == GI_TYPE_TAG_UTF8 || itag == GI_TYPE_TAG_FILENAME)
        {
          gchar **strv = *(gchar ***)((void *)(base + offset));
          return pygi_strv_to_py_list (strv, GI_TRANSFER_NOTHING);
        }
      if (itag == GI_TYPE_TAG_INTERFACE)
        {
          g_autoptr (GIBaseInfo) iinfo = gi_type_info_get_interface (inner_ti);
          gpointer *arr = *(gpointer **)((void *)(base + offset));
          gsize len = 0;
          if (arr != NULL)
            while (arr[len] != NULL)
              len++;
          PyObject *list = PyList_New ((Py_ssize_t)len);
          if (list == NULL)
            return NULL;
          if (iinfo == NULL || (!GI_IS_STRUCT_INFO (iinfo) && !GI_IS_UNION_INFO (iinfo)))
            return list;
          GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iinfo);
          PyObject *cls = record_build_class_for_info (iinfo, parent);
          if (cls == NULL)
            {
              Py_DECREF (list);
              return NULL;
            }
          for (gsize i = 0; i < len; i++)
            {
              PyObject *item = pygi_boxed_new_alias (cls, arr[i], gtype, parent);
              if (item == NULL)
                {
                  Py_DECREF (cls);
                  Py_DECREF (list);
                  return NULL;
                }
              PyList_SET_ITEM (list, (Py_ssize_t)i, item);
            }
          Py_DECREF (cls);
          return list;
        }
    }

  size_t fixed = 0;
  if (gi_type_info_get_array_fixed_size (fti, &fixed) && fixed > 0)
    {
      PyGIContainerElement element;
      if (pygi_container_element_init (&element, inner_ti) != 0)
        return NULL;
      gsize elem_size = pygi_container_element_inline_size (&element);
      if (elem_size == 0)
        {
          PyErr_SetString (PyExc_NotImplementedError, "unsupported fixed-array element size");
          return NULL;
        }
      PyObject *list = PyList_New ((Py_ssize_t)fixed);
      if (list == NULL)
        return NULL;
      char *array = base + offset;
      for (size_t i = 0; i < fixed; i++)
        {
          PyObject *item
              = pygi_container_element_inline_to_py (&element, array + ((gsize)i * elem_size));
          if (item == NULL)
            {
              Py_DECREF (list);
              return NULL;
            }
          PyList_SET_ITEM (list, (Py_ssize_t)i, item);
        }
      return list;
    }
  PyErr_SetString (PyExc_NotImplementedError,
                   "array field shape (e.g. length-annotated C array) not implemented");
  return NULL;
}

static int
array_field_from_py (GITypeInfo *fti, char *base, size_t offset, PyObject *value)
{
  if (gi_type_info_get_array_type (fti) != GI_ARRAY_TYPE_C)
    return -1;

  g_autoptr (GITypeInfo) inner_ti = gi_type_info_get_param_type (fti, 0);
  if (inner_ti == NULL)
    return -1;

  if (gi_type_info_is_zero_terminated (fti))
    {
      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      if (itag == GI_TYPE_TAG_UTF8 || itag == GI_TYPE_TAG_FILENAME)
        {
          PyObject *seq = PySequence_Fast (value, "expected a sequence of strings");
          if (seq == NULL)
            return -1;
          Py_ssize_t len = PySequence_Fast_GET_SIZE (seq);
          gchar **strv = g_new0 (gchar *, (gsize)len + 1);
          for (Py_ssize_t i = 0; i < len; i++)
            {
              PyObject *item = PySequence_Fast_GET_ITEM (seq, i);
              if (!PyUnicode_Check (item))
                {
                  Py_DECREF (seq);
                  g_strfreev (strv);
                  PyErr_SetString (PyExc_TypeError, "expected a sequence of strings");
                  return -1;
                }
              const char *s = PyUnicode_AsUTF8 (item);
              if (s == NULL)
                {
                  Py_DECREF (seq);
                  g_strfreev (strv);
                  return -1;
                }
              strv[i] = g_strdup (s);
            }
          Py_DECREF (seq);
          gchar ***slot = (gchar ***)(void *)(base + offset);
          g_strfreev (*slot);
          *slot = strv;
          return 0;
        }
    }

  size_t fixed = 0;
  if (gi_type_info_get_array_fixed_size (fti, &fixed) && fixed > 0)
    {
      PyObject *seq = PySequence_Fast (value, "expected a sequence");
      if (seq == NULL)
        return -1;
      Py_ssize_t len = PySequence_Fast_GET_SIZE (seq);
      if (len != (Py_ssize_t)fixed)
        {
          Py_DECREF (seq);
          PyErr_Format (PyExc_ValueError,
                        "expected fixed array of length %zu, got %zd",
                        fixed,
                        len);
          return -1;
        }
      PyGIContainerElement element;
      if (pygi_container_element_init (&element, inner_ti) != 0)
        {
          Py_DECREF (seq);
          return -1;
        }
      gsize elem_size = pygi_container_element_inline_size (&element);
      if (elem_size == 0)
        {
          Py_DECREF (seq);
          PyErr_SetString (PyExc_NotImplementedError, "unsupported fixed array element type");
          return -1;
        }
      char *array = base + offset;
      for (size_t i = 0; i < fixed; i++)
        {
          PyObject *item = PySequence_Fast_GET_ITEM (seq, (Py_ssize_t)i);
          if (pygi_container_element_inline_from_py (&element,
                                                     item,
                                                     GI_TRANSFER_NOTHING,
                                                     array + ((gsize)i * elem_size))
              != 0)
            {
              Py_DECREF (seq);
              return -1;
            }
        }
      Py_DECREF (seq);
      return 0;
    }

  PyErr_SetString (PyExc_NotImplementedError, "unsupported array field");
  return -1;
}

static PyObject *
field_to_py (GITypeInfo *fti, char *base, size_t offset, PyObject *parent)
{
  GITypeTag ftag = gi_type_info_get_tag (fti);
  if (ftag == GI_TYPE_TAG_VOID)
    {
      gpointer ptr = *(gpointer *)(base + offset);
      if (ptr == NULL)
        Py_RETURN_NONE;
      return PyLong_FromUnsignedLongLong ((unsigned long long)(uintptr_t)ptr);
    }
  if (ftag == GI_TYPE_TAG_ARRAY)
    return array_field_to_py (fti, base, offset, parent);
  if (ftag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo == NULL)
        return NULL;
      if (GI_IS_ENUM_INFO (finfo) || GI_IS_FLAGS_INFO (finfo))
        {
          GITypeTag stag = gi_enum_info_get_storage_type ((GIEnumInfo *)finfo);
          return pygi_primitive_storage_to_py (stag, base + offset);
        }
      if (GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo))
        {
          GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)finfo);
          gpointer field_ptr = gi_type_info_is_pointer (fti) ? *(gpointer *)(base + offset)
                                                             : (gpointer)(base + offset);
          if (field_ptr == NULL)
            Py_RETURN_NONE;
          PyObject *cls = record_build_class_for_info (finfo, parent);
          if (cls == NULL)
            return NULL;
          PyObject *out = pygi_boxed_new_alias (cls, field_ptr, gtype, parent);
          Py_DECREF (cls);
          return out;
        }
      if (GI_IS_OBJECT_INFO (finfo) || GI_IS_INTERFACE_INFO (finfo))
        {
          gpointer ptr = *(gpointer *)(base + offset);
          if (ptr == NULL)
            Py_RETURN_NONE;
          if (GI_IS_REGISTERED_TYPE_INFO (finfo))
            {
              GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)finfo);
              return pygi_gobject_to_py_as_gtype ((GObject *)ptr, gtype, GI_TRANSFER_NOTHING);
            }
        }
    }

  PyGIType field_type = { 0 };
  if (pygi_type_from_gi (fti, &field_type) == 0 && pygi_type_is_direct_storage (&field_type))
    return pygi_marshal_to_py (&(PyGIMarshalSlot){
        .type = fti,
        .pygi_type = &field_type,
        .transfer = GI_TRANSFER_NOTHING,
        .transfer_set = true,
        .kind = PYGI_MARSHAL_TARGET_MEMORY,
        .target.memory = base + offset,
    });

  PyErr_Format (PyExc_NotImplementedError, "unsupported field type tag %d", (int)ftag);
  return NULL;
}

static int
field_from_py (GITypeInfo *fti, char *base, size_t offset, PyObject *value)
{
  GITypeTag ftag = gi_type_info_get_tag (fti);
  if (ftag == GI_TYPE_TAG_ARRAY)
    return array_field_from_py (fti, base, offset, value);
  if (ftag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo != NULL && (GI_IS_ENUM_INFO (finfo) || GI_IS_FLAGS_INFO (finfo)))
        {
          GITypeTag stag = gi_enum_info_get_storage_type ((GIEnumInfo *)finfo);
          return pygi_py_to_primitive_storage (value, stag, base + offset);
        }
      if (finfo != NULL && (GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo)))
        {
          if (value == Py_None)
            {
              if (!gi_type_info_is_pointer (fti))
                {
                  PyErr_SetString (PyExc_TypeError, "inline struct fields do not accept None");
                  return -1;
                }
              *(gpointer *)(base + offset) = NULL;
              return 0;
            }

          gpointer boxed_ptr = NULL;
          if (pygi_boxed_get (value, &boxed_ptr) != 0)
            return -1;

          if (gi_type_info_is_pointer (fti))
            {
              *(gpointer *)(base + offset) = boxed_ptr;
              return 0;
            }

          gsize size = record_info_size (finfo);
          if (size == 0)
            {
              PyErr_SetString (PyExc_RuntimeError,
                               "cannot write inline struct field with unknown size");
              return -1;
            }
          memcpy (base + offset, boxed_ptr, size);
          return 0;
        }
    }

  PyGIType field_type = { 0 };
  if (pygi_type_from_gi (fti, &field_type) == 0 && pygi_type_is_direct_storage (&field_type))
    return pygi_marshal_from_py (value,
                                 &(PyGIMarshalSlot){
                                     .type = fti,
                                     .pygi_type = &field_type,
                                     .transfer = GI_TRANSFER_NOTHING,
                                     .transfer_set = true,
                                     .kind = PYGI_MARSHAL_TARGET_MEMORY,
                                     .target.memory = base + offset,
                                 });

  PyErr_Format (PyExc_NotImplementedError, "unsupported field type tag %d", (int)ftag);
  return -1;
}

PyObject *
py_record_new (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "OO", &cls, &capsule))
    return NULL;
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "record_new: cls must be a type");
      return NULL;
    }
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  if (!GI_IS_STRUCT_INFO (info) && !GI_IS_UNION_INFO (info))
    {
      PyErr_SetString (PyExc_TypeError, "record_new: expected struct or union info");
      return NULL;
    }
  gsize size = record_info_size (info);
  if (size == 0)
    size = sizeof (void *);
  gpointer boxed = g_malloc0 (size);
  if (boxed == NULL)
    return PyErr_NoMemory ();
  PyObject *self = ((PyTypeObject *)cls)->tp_alloc ((PyTypeObject *)cls, 0);
  if (self == NULL)
    {
      g_free (boxed);
      return NULL;
    }
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  me->boxed = boxed;
  me->gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)info);
  me->borrowed = 0;
  me->heap_allocated = 1;
  me->size = size;
  me->py_dict = NULL;
  me->parent = NULL;
  return self;
}

static PyObject *
event_source_call_method (GSource *source, const char *name, PyObject *args)
{
  PyGIEventSource *event_source = (PyGIEventSource *)source;
  if (event_source->py_wrapper == NULL)
    Py_RETURN_NONE;

  PyObject *method = PyObject_GetAttrString (event_source->py_wrapper, name);
  if (method == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          Py_RETURN_NONE;
        }
      return NULL;
    }

  PyObject *result
      = args == NULL ? PyObject_CallNoArgs (method) : PyObject_CallObject (method, args);
  Py_DECREF (method);
  return result;
}

static gboolean
event_source_result_as_bool (PyObject *result, gboolean fallback)
{
  if (result == Py_None)
    return fallback;

  int truth = PyObject_IsTrue (result);
  if (truth < 0)
    {
      PyErr_Print ();
      return fallback;
    }
  return truth ? TRUE : FALSE;
}

static gboolean
event_source_prepare (GSource *source, gint *timeout_)
{
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *result = event_source_call_method (source, "prepare", NULL);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      if (timeout_ != NULL)
        *timeout_ = -1;
      return FALSE;
    }

  gboolean ready = FALSE;
  gint timeout = -1;
  if (PyTuple_Check (result) && PyTuple_GET_SIZE (result) == 2)
    {
      ready = event_source_result_as_bool (PyTuple_GET_ITEM (result, 0), FALSE);
      long timeout_long = PyLong_AsLong (PyTuple_GET_ITEM (result, 1));
      if (timeout_long == -1 && PyErr_Occurred ())
        PyErr_Print ();
      else
        timeout = (gint)timeout_long;
    }
  else
    ready = event_source_result_as_bool (result, FALSE);

  if (timeout_ != NULL)
    *timeout_ = timeout;
  Py_DECREF (result);
  PyGILState_Release (state);
  return ready;
}

static gboolean
event_source_check (GSource *source)
{
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *result = event_source_call_method (source, "check", NULL);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return FALSE;
    }
  gboolean ready = event_source_result_as_bool (result, FALSE);
  Py_DECREF (result);
  PyGILState_Release (state);
  return ready;
}

static gboolean
event_source_dispatch (GSource *source, GSourceFunc callback, gpointer user_data)
{
  (void)callback;
  (void)user_data;
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *dispatch_args = Py_BuildValue ("(OO)", Py_None, Py_None);
  if (dispatch_args == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return G_SOURCE_REMOVE;
    }

  PyObject *result = event_source_call_method (source, "dispatch", dispatch_args);
  Py_DECREF (dispatch_args);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return G_SOURCE_REMOVE;
    }

  gboolean keep = event_source_result_as_bool (result, G_SOURCE_REMOVE);
  Py_DECREF (result);
  PyGILState_Release (state);
  return keep ? G_SOURCE_CONTINUE : G_SOURCE_REMOVE;
}

static GSourceFuncs event_source_funcs = {
  .prepare = event_source_prepare,
  .check = event_source_check,
  .dispatch = event_source_dispatch,
  .finalize = NULL,
};

PyObject *
py_glib_event_source_new (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  if (!PyArg_ParseTuple (args, "O", &cls))
    return NULL;
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "glib_event_source_new: cls must be a type");
      return NULL;
    }

  GSource *source = g_source_new (&event_source_funcs, sizeof (PyGIEventSource));
  if (source == NULL)
    return PyErr_NoMemory ();

  PyObject *self = pygi_boxed_new (cls, source, g_source_get_type (), 1);
  if (self == NULL)
    {
      g_source_unref (source);
      return NULL;
    }
  ((PyGIEventSource *)source)->py_wrapper = self;
  return self;
}

PyObject *
py_record_copy (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  (void)module;
  PyObject *obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &obj))
    return NULL;
  gpointer ptr = NULL;
  if (pygi_boxed_get (obj, &ptr) != 0)
    return NULL;
  if (ptr == NULL)
    Py_RETURN_NONE;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)obj;
  if (me->gtype == 0)
    {
      PyErr_SetString (PyExc_TypeError, "record has no boxed GType");
      return NULL;
    }
  gpointer copy = g_boxed_copy (me->gtype, ptr);
  if (copy == NULL)
    Py_RETURN_NONE;
  return pygi_boxed_new ((PyObject *)Py_TYPE (obj), copy, me->gtype, 1);
}

PyObject *
py_record_pointer_equal (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  (void)module;
  PyObject *left = NULL;
  PyObject *right = NULL;
  if (!PyArg_ParseTuple (args, "OO", &left, &right))
    return NULL;
  gpointer left_ptr = NULL;
  gpointer right_ptr = NULL;
  if (pygi_boxed_get (left, &left_ptr) != 0)
    return NULL;
  if (pygi_boxed_get (right, &right_ptr) != 0)
    return NULL;
  if (left_ptr == right_ptr)
    Py_RETURN_TRUE;
  Py_RETURN_FALSE;
}

PyObject *
py_record_pointer_value (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  (void)module;
  PyObject *obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &obj))
    return NULL;
  gpointer ptr = NULL;
  if (pygi_boxed_get (obj, &ptr) != 0)
    return NULL;
  return PyLong_FromVoidPtr (ptr);
}

/* ── Fast primitive field descriptors ──────────────────────────────────────
 *
 * record_install_field_descriptors(cls, info) builds PyGetSetDef-backed
 * "getset_descriptor" entries for every readable primitive scalar field in
 * a struct/union GI info and installs them on `cls`.  Once installed, a
 * plain attribute lookup (tp_getattro dict walk) finds the descriptor before
 * RecordBase.__getattr__ is ever called, giving O(1) access with no GI walk.
 *
 * Lifetime: the FieldDescClosure* blocks must outlive the descriptors (which
 * live as long as the class has any reference).  We keep them alive by storing
 * a PyCapsule under __field_desc_bundle__ on the class dict.
 * ────────────────────────────────────────────────────────────────────────── */

#include "marshal/scalar.h"
#include "runtime/type-info.h"

typedef struct
{
  size_t offset;
  GITypeTag tag;
} FieldDescClosure;

static PyObject *
field_desc_getter (PyObject *self, void *closure)
{
  FieldDescClosure *fdc = (FieldDescClosure *)closure;
  gpointer base = NULL;
  if (pygi_boxed_get (self, &base) != 0)
    return NULL;
  if (base == NULL)
    Py_RETURN_NONE;
  return pygi_primitive_storage_to_py (fdc->tag, (const char *)base + fdc->offset);
}

static int
field_desc_setter (PyObject *self, PyObject *value, void *closure)
{
  if (value == NULL)
    {
      PyErr_SetString (PyExc_AttributeError, "cannot delete struct field");
      return -1;
    }
  FieldDescClosure *fdc = (FieldDescClosure *)closure;
  gpointer base = NULL;
  if (pygi_boxed_get (self, &base) != 0)
    return -1;
  if (base == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "cannot set field on detached record");
      return -1;
    }
  return pygi_py_to_primitive_storage (value, fdc->tag, (char *)base + fdc->offset);
}

static void
field_desc_bundle_destroy (PyObject *cap)
{
  GPtrArray *arr = (GPtrArray *)PyCapsule_GetPointer (cap, "_ginext_field_desc_bundle");
  if (arr != NULL)
    g_ptr_array_unref (arr);
}

PyObject *
py_record_install_field_descriptors (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "OO", &cls, &capsule))
    return NULL;
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "record_install_field_descriptors: cls must be a type");
      return NULL;
    }
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  if (!GI_IS_STRUCT_INFO (info) && !GI_IS_UNION_INFO (info))
    Py_RETURN_NONE; /* nothing to do for non-struct/union */

  /* bundle: GPtrArray* of FieldDescClosure* — kept alive by a PyCapsule
   * stored under __field_desc_bundle__ on the class dict.
   * Name strings are also kept in this array (as char* via g_strdup) so they
   * outlive the PyGetSetDef copies that PyDescr_NewGetSet makes internally. */
  GPtrArray *bundle = g_ptr_array_new_with_free_func (g_free);

  int n = gi_struct_or_union_n_fields (info);
  for (int fi = 0; fi < n; fi++)
    {
      g_autoptr (GIFieldInfo) field = (GIFieldInfo *)gi_struct_or_union_get_field (info, (guint)fi);
      if (field == NULL)
        continue;
      if (!(gi_field_info_get_flags (field) & GI_FIELD_IS_READABLE))
        continue;
      g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
      if (fti == NULL)
        continue;
      GITypeTag tag = gi_type_info_get_tag (fti);
      switch (tag)
        {
        case GI_TYPE_TAG_BOOLEAN:
        case GI_TYPE_TAG_INT8:
        case GI_TYPE_TAG_UINT8:
        case GI_TYPE_TAG_INT16:
        case GI_TYPE_TAG_UINT16:
        case GI_TYPE_TAG_INT32:
        case GI_TYPE_TAG_UINT32:
        case GI_TYPE_TAG_INT64:
        case GI_TYPE_TAG_UINT64:
        case GI_TYPE_TAG_FLOAT:
        case GI_TYPE_TAG_DOUBLE:
          break;
        default:
          continue; /* skip non-primitive fields */
        }

      const char *raw_name = gi_base_info_get_name ((GIBaseInfo *)field);
      if (raw_name == NULL)
        continue;
      size_t offset = gi_field_info_get_offset (field);

      /* Allocate FieldDescClosure + name copy into bundle so the capsule
       * destructor frees them together. */
      FieldDescClosure *fdc = g_new0 (FieldDescClosure, 1);
      fdc->offset = offset;
      fdc->tag = tag;
      g_ptr_array_add (bundle, fdc);

      char *name_copy = g_strdup (raw_name);
      g_ptr_array_add (bundle, name_copy);

      /* PyDescr_NewGetSet stores the PyGetSetDef* by pointer, not by value,
       * so the def must be heap-allocated and outlive the descriptor. */
      PyGetSetDef *def = g_new0 (PyGetSetDef, 1);
      def->name = name_copy;
      def->get = field_desc_getter;
      def->set = field_desc_setter;
      def->doc = NULL;
      def->closure = (void *)fdc;
      g_ptr_array_add (bundle, def);
      PyObject *desc = PyDescr_NewGetSet ((PyTypeObject *)cls, def);
      if (desc == NULL)
        {
          g_ptr_array_unref (bundle);
          return NULL;
        }
      int rc = PyDict_SetItemString (((PyTypeObject *)cls)->tp_dict, name_copy, desc);
      Py_DECREF (desc);
      if (rc != 0)
        {
          g_ptr_array_unref (bundle);
          return NULL;
        }
    }

  if (bundle->len > 0)
    {
      PyObject *cap
          = PyCapsule_New (bundle, "_ginext_field_desc_bundle", field_desc_bundle_destroy);
      if (cap == NULL)
        {
          g_ptr_array_unref (bundle);
          return NULL;
        }
      int rc = PyDict_SetItemString (((PyTypeObject *)cls)->tp_dict, "__field_desc_bundle__", cap);
      Py_DECREF (cap);
      if (rc != 0)
        return NULL;
      PyType_Modified ((PyTypeObject *)cls);
    }
  else
    {
      g_ptr_array_unref (bundle);
    }

  Py_RETURN_NONE;
}

/* record_field_names(info) -> tuple[str, ...]
 * The readable primitive-scalar field names of a struct/union, in declaration
 * order. Used to set __match_args__ so records support positional pattern
 * matching, e.g. `case Color(red, green, blue)` — where field order is the
 * natural contract, mirroring the C layout.
 *
 * Restricted to the same readable primitive scalars that
 * record_install_field_descriptors exposes as fast getset descriptors: those
 * are the safe, value-like fields. Pointer/array/nested/interface fields are
 * excluded — a positional `case` reads *every* listed attribute, and routing
 * those through the generic field getter can fault on a freshly-zeroed record
 * (e.g. a NULL gpointer field). */
PyObject *
py_record_field_names (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "O", &capsule))
    return NULL;
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  if (!GI_IS_STRUCT_INFO (info) && !GI_IS_UNION_INFO (info))
    return PyTuple_New (0);

  int n = gi_struct_or_union_n_fields (info);
  PyObject *names = PyList_New (0);
  if (names == NULL)
    return NULL;
  for (int fi = 0; fi < n; fi++)
    {
      g_autoptr (GIFieldInfo) field = (GIFieldInfo *)gi_struct_or_union_get_field (info, (guint)fi);
      if (field == NULL)
        continue;
      if (!(gi_field_info_get_flags (field) & GI_FIELD_IS_READABLE))
        continue;
      g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
      if (fti == NULL)
        continue;
      switch (gi_type_info_get_tag (fti))
        {
        case GI_TYPE_TAG_BOOLEAN:
        case GI_TYPE_TAG_INT8:
        case GI_TYPE_TAG_UINT8:
        case GI_TYPE_TAG_INT16:
        case GI_TYPE_TAG_UINT16:
        case GI_TYPE_TAG_INT32:
        case GI_TYPE_TAG_UINT32:
        case GI_TYPE_TAG_INT64:
        case GI_TYPE_TAG_UINT64:
        case GI_TYPE_TAG_FLOAT:
        case GI_TYPE_TAG_DOUBLE:
          break;
        default:
          continue; /* skip non-primitive fields (see comment above) */
        }
      const char *raw_name = gi_base_info_get_name ((GIBaseInfo *)field);
      if (raw_name == NULL)
        continue;
      PyObject *s = PyUnicode_FromString (raw_name);
      if (s == NULL)
        {
          Py_DECREF (names);
          return NULL;
        }
      int rc = PyList_Append (names, s);
      Py_DECREF (s);
      if (rc != 0)
        {
          Py_DECREF (names);
          return NULL;
        }
    }
  PyObject *tuple = PyList_AsTuple (names);
  Py_DECREF (names);
  return tuple;
}

PyObject *
py_record_field_get (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *obj = NULL;
  PyObject *capsule = NULL;
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "OOs", &obj, &capsule, &name))
    return NULL;
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  gpointer ptr = NULL;
  if (pygi_boxed_get (obj, &ptr) != 0)
    return NULL;
  if (ptr == NULL)
    Py_RETURN_NONE;
  GIFieldInfo *field = NULL;
  if (!record_lookup_field (info, name, &field))
    {
      PyErr_Format (PyExc_AttributeError, "%s has no field %s", gi_base_info_get_name (info), name);
      return NULL;
    }
  if (!(gi_field_info_get_flags (field) & GI_FIELD_IS_READABLE))
    {
      gi_base_info_unref ((GIBaseInfo *)field);
      PyErr_Format (PyExc_AttributeError, "field %s is not readable", name);
      return NULL;
    }
  g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
  size_t offset = gi_field_info_get_offset (field);
  if (GI_IS_UNION_INFO (info) && !(gi_field_info_get_flags (field) & GI_FIELD_IS_WRITABLE)
      && gi_type_info_get_tag (fti) == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo != NULL && (GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo)))
        {
          gi_base_info_unref ((GIBaseInfo *)field);
          PyErr_Format (PyExc_AttributeError, "field %s is not readable", name);
          return NULL;
        }
    }
  if (GI_IS_UNION_INFO (info) && gi_type_info_get_tag (fti) == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo != NULL && (GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo)))
        {
          PyObject *out = union_interface_field_shadow_to_py (fti, (char *)ptr, offset, obj, name);
          gi_base_info_unref ((GIBaseInfo *)field);
          return out;
        }
    }
  PyObject *out = field_to_py (fti, (char *)ptr, offset, obj);
  gi_base_info_unref ((GIBaseInfo *)field);
  if (out == NULL && !PyErr_Occurred ())
    PyErr_Format (PyExc_NotImplementedError, "field %s: marshalling not implemented", name);
  return out;
}

PyObject *
py_record_field_set (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *obj = NULL;
  PyObject *capsule = NULL;
  const char *name = NULL;
  PyObject *value = NULL;
  if (!PyArg_ParseTuple (args, "OOsO", &obj, &capsule, &name, &value))
    return NULL;
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  gpointer ptr = NULL;
  if (pygi_boxed_get (obj, &ptr) != 0)
    return NULL;
  if (ptr == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "cannot set field on detached boxed value");
      return NULL;
    }
  GIFieldInfo *field = NULL;
  if (!record_lookup_field (info, name, &field))
    {
      PyErr_Format (PyExc_AttributeError, "%s has no field %s", gi_base_info_get_name (info), name);
      return NULL;
    }
  if (!(gi_field_info_get_flags (field) & GI_FIELD_IS_WRITABLE))
    {
      gi_base_info_unref ((GIBaseInfo *)field);
      PyErr_Format (PyExc_AttributeError, "field %s is not writable", name);
      return NULL;
    }
  g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
  size_t offset = gi_field_info_get_offset (field);
  int rc = field_from_py (fti, (char *)ptr, offset, value);
  gi_base_info_unref ((GIBaseInfo *)field);
  if (rc != 0)
    return NULL;
  Py_RETURN_NONE;
}

/* StructInfo.anonymous_union_offset(prev_field, align) /
 * UnionInfo.anonymous_union_offset(...) — byte offset at which an anonymous
 * union following `prev_field` begins. METH_VARARGS method on both types. */
PyObject *
ginext_anonymous_union_offset_method (PyObject *self, PyObject *args)
{
  const char *previous_field_name = NULL;
  Py_ssize_t align = 1;
  if (!PyArg_ParseTuple (args, "sn", &previous_field_name, &align))
    return NULL;
  if (align <= 0)
    align = 1;
  GIBaseInfo *info = PYGI_INFO (self);
  GIFieldInfo *field = NULL;
  if (!record_lookup_field (info, previous_field_name, &field))
    {
      PyErr_Format (PyExc_AttributeError,
                    "%s has no field %s",
                    gi_base_info_get_name (info),
                    previous_field_name);
      return NULL;
    }
  size_t offset = gi_field_info_get_offset (field);
  size_t size_bits = gi_field_info_get_size (field);
  gi_base_info_unref ((GIBaseInfo *)field);
  size_t size = (size_bits + 7u) / 8u;
  if (size == 0)
    size = 1;
  size_t end = offset + size;
  size_t mask = (size_t)align - 1u;
  if (((size_t)align & mask) == 0)
    end = (end + mask) & ~mask;
  else
    {
      size_t rem = end % (size_t)align;
      if (rem != 0)
        end += (size_t)align - rem;
    }
  return PyLong_FromSize_t (end);
}

PyObject *
py_record_ensure_size (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *obj = NULL;
  Py_ssize_t min_size = 0;
  if (!PyArg_ParseTuple (args, "On", &obj, &min_size))
    return NULL;
  if (!pygi_boxed_check (obj))
    {
      PyErr_SetString (PyExc_TypeError, "expected boxed record");
      return NULL;
    }
  if (min_size < 0)
    {
      PyErr_SetString (PyExc_ValueError, "negative record size");
      return NULL;
    }
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)obj;
  if (me->size >= (gsize)min_size)
    Py_RETURN_NONE;
  if (!me->heap_allocated || me->boxed == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "cannot resize borrowed record storage");
      return NULL;
    }
  gpointer resized = g_realloc (me->boxed, (gsize)min_size);
  if (resized == NULL)
    return PyErr_NoMemory ();
  memset ((char *)resized + me->size, 0, (gsize)min_size - me->size);
  me->boxed = resized;
  me->size = (gsize)min_size;
  return Py_NewRef (Py_None);
}

static char *
record_memory_checked (PyObject *obj, Py_ssize_t offset, size_t width)
{
  gpointer ptr = NULL;
  if (pygi_boxed_get (obj, &ptr) != 0)
    return NULL;
  if (ptr == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "record is detached");
      return NULL;
    }
  if (offset < 0)
    {
      PyErr_SetString (PyExc_ValueError, "negative record memory offset");
      return NULL;
    }
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)obj;
  if (me->size != 0 && (size_t)offset + width > me->size)
    {
      PyErr_SetString (PyExc_ValueError, "record memory access is out of bounds");
      return NULL;
    }
  return (char *)ptr + offset;
}

PyObject *
py_record_memory_get (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *obj = NULL;
  Py_ssize_t offset = 0;
  const char *type_name = NULL;
  if (!PyArg_ParseTuple (args, "Ons", &obj, &offset, &type_name))
    return NULL;

  if (strcmp (type_name, "gpointer") == 0 || strcmp (type_name, "gconstpointer") == 0)
    {
      char *slot = record_memory_checked (obj, offset, sizeof (gpointer));
      if (slot == NULL)
        return NULL;
      gpointer value = *(gpointer *)slot;
      if (value == NULL)
        Py_RETURN_NONE;
      return PyLong_FromVoidPtr (value);
    }
  if (strcmp (type_name, "gdouble") == 0 || strcmp (type_name, "double") == 0)
    {
      char *slot = record_memory_checked (obj, offset, sizeof (double));
      if (slot == NULL)
        return NULL;
      return PyFloat_FromDouble (*(double *)slot);
    }
  if (strcmp (type_name, "glong") == 0 || strcmp (type_name, "long") == 0)
    {
      char *slot = record_memory_checked (obj, offset, sizeof (long));
      if (slot == NULL)
        return NULL;
      return PyLong_FromLong (*(long *)slot);
    }
  if (strcmp (type_name, "gint") == 0 || strcmp (type_name, "int") == 0)
    {
      char *slot = record_memory_checked (obj, offset, sizeof (int));
      if (slot == NULL)
        return NULL;
      return PyLong_FromLong (*(int *)slot);
    }

  PyErr_Format (PyExc_NotImplementedError, "unsupported anonymous union field type %s", type_name);
  return NULL;
}

PyObject *
py_record_memory_set (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *obj = NULL;
  Py_ssize_t offset = 0;
  const char *type_name = NULL;
  PyObject *value = NULL;
  if (!PyArg_ParseTuple (args, "OnsO", &obj, &offset, &type_name, &value))
    return NULL;

  if (strcmp (type_name, "gpointer") == 0 || strcmp (type_name, "gconstpointer") == 0)
    {
      char *slot = record_memory_checked (obj, offset, sizeof (gpointer));
      if (slot == NULL)
        return NULL;
      if (value == Py_None)
        *(gpointer *)slot = NULL;
      else
        *(gpointer *)slot = PyLong_AsVoidPtr (value);
      if (PyErr_Occurred ())
        return NULL;
      Py_RETURN_NONE;
    }
  if (strcmp (type_name, "gdouble") == 0 || strcmp (type_name, "double") == 0)
    {
      char *slot = record_memory_checked (obj, offset, sizeof (double));
      if (slot == NULL)
        return NULL;
      double v = PyFloat_AsDouble (value);
      if (PyErr_Occurred ())
        return NULL;
      *(double *)slot = v;
      Py_RETURN_NONE;
    }
  if (strcmp (type_name, "glong") == 0 || strcmp (type_name, "long") == 0)
    {
      char *slot = record_memory_checked (obj, offset, sizeof (long));
      if (slot == NULL)
        return NULL;
      long v = PyLong_AsLong (value);
      if (PyErr_Occurred ())
        return NULL;
      *(long *)slot = v;
      Py_RETURN_NONE;
    }
  if (strcmp (type_name, "gint") == 0 || strcmp (type_name, "int") == 0)
    {
      char *slot = record_memory_checked (obj, offset, sizeof (int));
      if (slot == NULL)
        return NULL;
      long v = PyLong_AsLong (value);
      if (PyErr_Occurred ())
        return NULL;
      *(int *)slot = (int)v;
      Py_RETURN_NONE;
    }

  PyErr_Format (PyExc_NotImplementedError, "unsupported anonymous union field type %s", type_name);
  return NULL;
}

PyObject *
py_register_boxed_class (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  unsigned long long gtype_arg = 0;
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "OKO", &cls, &gtype_arg, &capsule))
    return NULL;
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "register_boxed_class: cls must be a type");
      return NULL;
    }
  if (boxed_classes_by_gtype == NULL)
    {
      boxed_classes_by_gtype = PyDict_New ();
      if (boxed_classes_by_gtype == NULL)
        return NULL;
    }
  if (gtype_arg != 0)
    {
      PyObject *profile_name = profile_name_from_object (cls);
      if (profile_name == NULL)
        return NULL;
      PyObject *key = boxed_registry_key ((GType)gtype_arg, profile_name);
      Py_DECREF (profile_name);
      if (key == NULL)
        return NULL;
      if (PyDict_SetItem (boxed_classes_by_gtype, key, cls) < 0)
        {
          Py_DECREF (key);
          return NULL;
        }
      Py_DECREF (key);
    }
  (void)capsule;
  Py_RETURN_NONE;
}

void
pygi_pybuffer_release_destroy_notify (gpointer data)
{
  Py_buffer *view = (Py_buffer *)data;
  if (view != NULL)
    {
      PyBuffer_Release (view);
      g_free (view);
    }
}

typedef struct
{
  GIArgInfo *arg_info;
  GITypeInfo *type_info;
  GITypeInfo *array_elem_info;
  GITypeTag tag;
  GITypeTag array_elem_tag;
  GIDirection direction;
  GITransfer transfer;
  ffi_type *ffi_type;
  int array_length_arg;
  int length_owner_array;
  gboolean is_closure;
  GType wrapper_gtype;
} PyGICallbackArgPlan;

typedef struct
{
  PyObject *callable;
  PyObject *py_user_data;
  PyObject *namespace;
  GICallableInfo *callback_info;
  GITypeInfo *return_type;
  GITypeTag return_tag;
  GITransfer return_transfer;
  int n_args;
  int n_out_args;
  /* Positional arity of the Python callable, cached at closure
   * creation. -1 means uninspectable or accepts *args — trampoline
   * passes the full arg list. Otherwise the trampoline trims to this
   * length so a `def cb(): ...` against a C-side signature with
   * `user_data` doesn't surface "got 1 arg, expected 0". */
  int callable_arity;
  PyGICallbackArgPlan *args;
  ffi_type **ffi_arg_types;
  ffi_type *ffi_return_type;
  ffi_cif cif;
  ffi_closure *closure;
  void *code;
  GIScopeType scope;
  gboolean include_array_length_args;
  /* For transfer-nothing utf8/filename callback returns: we strdup the
   * Python str into pinned_return and free it on the next call or on
   * closure teardown, since the caller won't free it. */
  char *pinned_return;
} PyGICallbackClosure;

typedef struct
{
  PyObject_HEAD PyGICompiledCallable *compiled;
  GICallableInfo *callback_info;
  PyObject *namespace;
  char *qualified_name;
  Py_ssize_t user_data_py_index;
  gpointer user_data_ptr;
} PyGIReverseCallback;

static GMutex callback_deferred_free_lock;
static GList *callback_deferred_free_list = NULL;
PyTypeObject *ginext_reverse_callback_type = NULL;

static void
callback_closure_free (PyGICallbackClosure *closure);

static void
callback_closure_release_py_refs (PyGICallbackClosure *closure)
{
  if (closure == NULL)
    return;
  Py_CLEAR (closure->callable);
  Py_CLEAR (closure->py_user_data);
  Py_CLEAR (closure->namespace);
}

static void
reverse_callback_dealloc (PyObject *self)
{
  PyGIReverseCallback *callback = (PyGIReverseCallback *)self;
  pygi_compiled_callable_destroy_for_ffi (callback->compiled);
  g_clear_pointer (&callback->callback_info, gi_base_info_unref);
  Py_CLEAR (callback->namespace);
  free (callback->qualified_name);
  Py_TYPE (self)->tp_free (self);
}

static PyObject *
reverse_callback_repr (PyObject *self)
{
  PyGIReverseCallback *callback = (PyGIReverseCallback *)self;
  return PyUnicode_FromFormat ("<callback '%s'>",
                               callback->qualified_name != NULL ? callback->qualified_name : "?");
}

static PyObject *
reverse_callback_call (PyObject *self, PyObject *args, PyObject *kw)
{
  PyGIReverseCallback *callback = (PyGIReverseCallback *)self;
  if (kw != NULL && PyDict_GET_SIZE (kw) != 0)
    {
      PyErr_SetString (PyExc_TypeError, "callback wrappers do not accept keyword arguments");
      return NULL;
    }

  Py_ssize_t nargs = PyTuple_GET_SIZE (args);
  Py_ssize_t full_nargs = nargs + (callback->user_data_py_index >= 0 ? 1 : 0);
  PyObject **argv = g_new0 (PyObject *, (gsize)(full_nargs > 0 ? full_nargs : 1));
  if (argv == NULL)
    return PyErr_NoMemory ();

  if (callback->user_data_py_index >= 0)
    {
      PyObject *user_data = callback->user_data_ptr != NULL
                                ? PyLong_FromVoidPtr (callback->user_data_ptr)
                                : Py_NewRef (Py_None);
      if (user_data == NULL)
        {
          g_free (argv);
          return NULL;
        }

      Py_ssize_t src = 0;
      for (Py_ssize_t dst = 0; dst < full_nargs; dst++)
        {
          if (dst == callback->user_data_py_index)
            argv[dst] = user_data;
          else
            argv[dst] = PyTuple_GET_ITEM (args, src++);
        }
    }
  else
    {
      for (Py_ssize_t i = 0; i < nargs; i++)
        argv[i] = PyTuple_GET_ITEM (args, i);
    }

  PyGIMethodDescriptor descriptor = {
    .compiled = callback->compiled,
    .info = (GIFunctionInfo *)callback->callback_info,
    .has_self = 0,
    .qualified_name = callback->qualified_name,
    .namespace = callback->namespace,
  };
  PyObject *result
      = pygi_method_descriptor_call_ffi_invoke (&descriptor, argv, (size_t)full_nargs, NULL);
  if (callback->user_data_py_index >= 0)
    Py_DECREF (argv[callback->user_data_py_index]);
  g_free (argv);
  return result;
}

static ffi_type *
callback_ffi_type_for_tag (GITypeTag tag, GITypeInfo *ti, gboolean pointer)
{
  if (pointer)
    return &ffi_type_pointer;
  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
      if (iface != NULL && (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)))
        {
          GITypeTag storage = gi_enum_info_get_storage_type ((GIEnumInfo *)iface);
          return callback_ffi_type_for_tag (storage, ti, FALSE);
        }
      return &ffi_type_pointer;
    }
  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      return &ffi_type_void;
    case GI_TYPE_TAG_BOOLEAN:
      return &ffi_type_sint32;
    case GI_TYPE_TAG_INT8:
      return &ffi_type_sint8;
    case GI_TYPE_TAG_UINT8:
      return &ffi_type_uint8;
    case GI_TYPE_TAG_INT16:
      return &ffi_type_sint16;
    case GI_TYPE_TAG_UINT16:
      return &ffi_type_uint16;
    case GI_TYPE_TAG_INT32:
      return &ffi_type_sint32;
    case GI_TYPE_TAG_UINT32:
    case GI_TYPE_TAG_UNICHAR:
      return &ffi_type_uint32;
    case GI_TYPE_TAG_INT64:
      return &ffi_type_sint64;
    case GI_TYPE_TAG_UINT64:
    case GI_TYPE_TAG_GTYPE:
      return &ffi_type_uint64;
    case GI_TYPE_TAG_FLOAT:
      return &ffi_type_float;
    case GI_TYPE_TAG_DOUBLE:
      return &ffi_type_double;
    default:
      return &ffi_type_pointer;
    }
}

static gboolean
callable_info_find_user_data_arg (GICallableInfo *callback_info, Py_ssize_t *out_py_index)
{
  int n_args = (int)gi_callable_info_get_n_args (callback_info);
  Py_ssize_t py_index = 0;
  for (int i = 0; i < n_args; i++)
    {
      g_autoptr (GIArgInfo) arg_info = gi_callable_info_get_arg (callback_info, (guint)i);
      if (arg_info == NULL || gi_arg_info_get_direction (arg_info) == GI_DIRECTION_OUT)
        continue;

      g_autoptr (GITypeInfo) type_info = gi_arg_info_get_type_info (arg_info);
      const char *name = gi_base_info_get_name ((GIBaseInfo *)arg_info);
      if (type_info != NULL && gi_type_info_get_tag (type_info) == GI_TYPE_TAG_VOID
          && gi_type_info_is_pointer (type_info) && name != NULL
          && (strcmp (name, "user_data") == 0 || strcmp (name, "data") == 0))
        {
          *out_py_index = py_index;
          return TRUE;
        }
      py_index++;
    }
  return FALSE;
}

static PyObject *
reverse_callback_new (PyObject *namespace,
                      GICallableInfo *callback_info,
                      gpointer callback_ptr,
                      gpointer user_data_ptr)
{
  if (ginext_reverse_callback_type == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "reverse callback type not initialized");
      return NULL;
    }

  const char *namespace_name = gi_base_info_get_namespace ((GIBaseInfo *)callback_info);
  const char *name = gi_base_info_get_name ((GIBaseInfo *)callback_info);
  g_autofree char *qualified_name = g_strdup_printf ("%s.%s",
                                                     namespace_name != NULL ? namespace_name : "?",
                                                     name != NULL ? name : "callback");
  PyGICompiledCallable *compiled
      = pygi_compile_callable_for_ffi_target (callback_info, callback_ptr, 0, qualified_name);
  if (compiled == NULL)
    return NULL;

  PyObject *obj = PyType_GenericAlloc (ginext_reverse_callback_type, 0);
  if (obj == NULL)
    {
      pygi_compiled_callable_destroy_for_ffi (compiled);
      return NULL;
    }

  PyGIReverseCallback *callback = (PyGIReverseCallback *)obj;
  callback->compiled = compiled;
  callback->callback_info = (GICallableInfo *)gi_base_info_ref ((GIBaseInfo *)callback_info);
  callback->namespace = Py_NewRef (namespace);
  callback->qualified_name = g_strdup (qualified_name);
  callback->user_data_ptr = user_data_ptr;
  callback->user_data_py_index = -1;
  if (callback->qualified_name == NULL)
    {
      Py_DECREF (obj);
      return PyErr_NoMemory ();
    }
  if (!callable_info_find_user_data_arg (callback_info, &callback->user_data_py_index))
    callback->user_data_py_index = -1;
  return obj;
}

/* Returns the positional-arg count of a Python callable, or -1 for
 * *args / uninspectable. Mirrors signal.py:_callback_arity. */
static int
callback_inspect_arity (PyObject *callable)
{
  static PyObject *signature_fn = NULL;
  static PyObject *pos_only_kind = NULL;
  static PyObject *pos_or_kw_kind = NULL;
  static PyObject *var_pos_kind = NULL;
  if (signature_fn == NULL)
    {
      PyObject *mod = PyImport_ImportModule ("inspect");
      if (mod == NULL)
        {
          PyErr_Clear ();
          return -1;
        }
      signature_fn = PyObject_GetAttrString (mod, "signature");
      PyObject *param_cls = PyObject_GetAttrString (mod, "Parameter");
      Py_DECREF (mod);
      if (param_cls != NULL)
        {
          pos_only_kind = PyObject_GetAttrString (param_cls, "POSITIONAL_ONLY");
          pos_or_kw_kind = PyObject_GetAttrString (param_cls, "POSITIONAL_OR_KEYWORD");
          var_pos_kind = PyObject_GetAttrString (param_cls, "VAR_POSITIONAL");
          Py_DECREF (param_cls);
        }
      if (signature_fn == NULL || pos_only_kind == NULL || pos_or_kw_kind == NULL
          || var_pos_kind == NULL)
        {
          PyErr_Clear ();
          return -1;
        }
    }
  PyObject *sig = PyObject_CallOneArg (signature_fn, callable);
  if (sig == NULL)
    {
      PyErr_Clear ();
      return -1;
    }
  PyObject *params = PyObject_GetAttrString (sig, "parameters");
  Py_DECREF (sig);
  if (params == NULL)
    {
      PyErr_Clear ();
      return -1;
    }
  PyObject *values = PyObject_CallMethod (params, "values", NULL);
  Py_DECREF (params);
  if (values == NULL)
    {
      PyErr_Clear ();
      return -1;
    }
  PyObject *iter = PyObject_GetIter (values);
  Py_DECREF (values);
  if (iter == NULL)
    {
      PyErr_Clear ();
      return -1;
    }
  int arity = 0;
  PyObject *item;
  while ((item = PyIter_Next (iter)))
    {
      PyObject *kind = PyObject_GetAttrString (item, "kind");
      Py_DECREF (item);
      if (kind == NULL)
        break;
      if (kind == var_pos_kind)
        {
          Py_DECREF (kind);
          arity = -1;
          break;
        }
      if (kind == pos_only_kind || kind == pos_or_kw_kind)
        arity++;
      Py_DECREF (kind);
    }
  Py_DECREF (iter);
  if (PyErr_Occurred ())
    {
      PyErr_Clear ();
      return -1;
    }
  return arity;
}

static PyObject *
callback_bound_arg_gtypes_obj (PyObject *callable)
{
  PyObject *bound = PyObject_GetAttrString (callable, "ginext_bound_callback_gtypes");
  if (bound != NULL)
    return bound;
  PyErr_Clear ();
  PyObject *func = PyObject_GetAttrString (callable, "__func__");
  if (func == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  bound = PyObject_GetAttrString (func, "ginext_bound_callback_gtypes");
  Py_DECREF (func);
  if (bound == NULL)
    PyErr_Clear ();
  return bound;
}

static int
callback_apply_bound_arg_gtypes (PyGICallbackClosure *closure)
{
  PyObject *bound = callback_bound_arg_gtypes_obj (closure->callable);
  if (bound == NULL)
    return 0;
  if (!PyTuple_Check (bound))
    {
      Py_DECREF (bound);
      return 0;
    }
  Py_ssize_t n = PyTuple_GET_SIZE (bound);
  Py_ssize_t limit = n < closure->n_args ? n : closure->n_args;
  for (Py_ssize_t i = 0; i < limit; i++)
    {
      unsigned long long raw = PyLong_AsUnsignedLongLong (PyTuple_GET_ITEM (bound, i));
      if (PyErr_Occurred ())
        {
          Py_DECREF (bound);
          return -1;
        }
      closure->args[i].wrapper_gtype = (GType)raw;
    }
  Py_DECREF (bound);
  return 0;
}

static gboolean
callback_arg_is_void_pointer (GIArgInfo *arg_info)
{
  g_autoptr (GITypeInfo) type_info = gi_arg_info_get_type_info (arg_info);
  return type_info != NULL && gi_type_info_get_tag (type_info) == GI_TYPE_TAG_VOID
         && gi_type_info_is_pointer (type_info);
}

static gboolean
callback_arg_is_closure (GICallableInfo *callback_info, int arg_index, GIArgInfo *arg_info)
{
  unsigned int closure_index = 0;
  if (gi_arg_info_get_closure_index (arg_info, &closure_index) && (int)closure_index == arg_index)
    return TRUE;

  const char *name = gi_base_info_get_name ((GIBaseInfo *)arg_info);
  if (name == NULL)
    return FALSE;
  if (arg_index != (int)gi_callable_info_get_n_args (callback_info) - 1)
    return FALSE;
  if (!callback_arg_is_void_pointer (arg_info))
    return FALSE;
  return strcmp (name, "user_data") == 0 || strcmp (name, "data") == 0;
}

static gboolean
callback_arg_is_trailing_user_data (PyGICallbackClosure *closure, int arg_index)
{
  if (closure == NULL || arg_index != closure->n_args - 1)
    return FALSE;
  PyGICallbackArgPlan *arg = &closure->args[arg_index];
  if (arg->direction != GI_DIRECTION_IN)
    return FALSE;
  if (arg->tag != GI_TYPE_TAG_VOID || !gi_type_info_is_pointer (arg->type_info))
    return FALSE;
  const char *name = gi_base_info_get_name ((GIBaseInfo *)arg->arg_info);
  if (name == NULL)
    return FALSE;
  return strcmp (name, "user_data") == 0 || strcmp (name, "data") == 0;
}

static PyGICallbackClosure *
callback_closure_alloc (PyObject *callable, GICallableInfo *callback_info)
{
  PyGICallbackClosure *closure = g_new0 (PyGICallbackClosure, 1);
  Py_INCREF (callable);
  closure->callable = callable;
  PyObject *namespace = pygi_namespace_context ();
  if (namespace == NULL)
    {
      callback_closure_release_py_refs (closure);
      g_free (closure);
      return NULL;
    }
  closure->namespace = Py_NewRef (namespace);
  closure->callable_arity = callback_inspect_arity (callable);
  closure->callback_info = (GICallableInfo *)gi_base_info_ref ((GIBaseInfo *)callback_info);
  closure->return_type = gi_callable_info_get_return_type (callback_info);
  closure->return_tag = gi_type_info_get_tag (closure->return_type);
  closure->return_transfer = gi_callable_info_get_caller_owns (callback_info);
  closure->ffi_return_type = callback_ffi_type_for_tag (
      closure->return_tag, closure->return_type,
      gi_type_info_is_pointer (closure->return_type));
  closure->n_args = (int)gi_callable_info_get_n_args (callback_info);
  closure->args = g_new0 (PyGICallbackArgPlan, (gsize)(closure->n_args > 0 ? closure->n_args : 1));
  closure->ffi_arg_types = g_new0 (ffi_type *, (gsize)(closure->n_args > 0 ? closure->n_args : 1));
  for (int i = 0; i < closure->n_args; i++)
    {
      closure->args[i].array_length_arg = -1;
      closure->args[i].length_owner_array = -1;
    }
  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      arg->arg_info = gi_callable_info_get_arg (callback_info, (guint)i);
      arg->type_info = gi_arg_info_get_type_info (arg->arg_info);
      arg->tag = gi_type_info_get_tag (arg->type_info);
      arg->direction = gi_arg_info_get_direction (arg->arg_info);
      arg->transfer = gi_arg_info_get_ownership_transfer (arg->arg_info);
      arg->is_closure = arg->direction == GI_DIRECTION_IN
                        && callback_arg_is_closure (callback_info, i, arg->arg_info);
      arg->ffi_type = callback_ffi_type_for_tag (
          arg->tag, arg->type_info,
          arg->direction != GI_DIRECTION_IN || gi_type_info_is_pointer (arg->type_info));
      closure->ffi_arg_types[i] = arg->ffi_type;
      if (arg->tag == GI_TYPE_TAG_ARRAY
          && gi_type_info_get_array_type (arg->type_info) == GI_ARRAY_TYPE_C)
        {
          arg->array_elem_info = gi_type_info_get_param_type (arg->type_info, 0);
          arg->array_elem_tag = arg->array_elem_info != NULL
                                    ? gi_type_info_get_tag (arg->array_elem_info)
                                    : GI_TYPE_TAG_VOID;
          unsigned int len_idx = 0;
          if (gi_type_info_get_array_length_index (arg->type_info, &len_idx)
              && len_idx < (unsigned int)closure->n_args)
            {
              arg->array_length_arg = (int)len_idx;
              closure->args[len_idx].length_owner_array = i;
            }
        }
    }
  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      if (arg->direction != GI_DIRECTION_IN && arg->length_owner_array < 0)
        closure->n_out_args++;
    }
  if (callback_apply_bound_arg_gtypes (closure) != 0)
    {
      callback_closure_free (closure);
      return NULL;
    }
  return closure;
}

static void
callback_closure_free (PyGICallbackClosure *closure)
{
  if (closure == NULL)
    return;
  if (closure->closure != NULL)
    {
      ffi_closure_free (closure->closure);
      closure->closure = NULL;
    }
  /* Py_CLEAR (not Py_XDECREF) so a re-entrant call from the dealloc
   * path doesn't dereference the same field twice. The destroy_notify
   * route (pygi_callback_closure_destroy) can fire from inside the
   * trampoline's own teardown when a notified-scope source drops its
   * last ref while the dispatch is still unwinding. */
  Py_CLEAR (closure->callable);
  Py_CLEAR (closure->py_user_data);
  if (closure->args != NULL)
    {
      for (int i = 0; i < closure->n_args; i++)
        {
          g_clear_pointer (&closure->args[i].arg_info, gi_base_info_unref);
          g_clear_pointer (&closure->args[i].type_info, gi_base_info_unref);
          g_clear_pointer (&closure->args[i].array_elem_info, gi_base_info_unref);
        }
    }
  g_free (closure->args);
  g_free (closure->ffi_arg_types);
  g_clear_pointer (&closure->return_type, gi_base_info_unref);
  g_clear_pointer (&closure->callback_info, gi_base_info_unref);
  g_clear_pointer (&closure->pinned_return, g_free);
  g_free (closure);
}

static void
callback_closure_enqueue_deferred_free (PyGICallbackClosure *closure)
{
  /* scope=async callbacks are one-shot. The trampoline drops Python refs
   * before returning, but defers ffi_closure_free because we are still
   * executing from the closure's code page at this point. The next callback
   * allocation, or module teardown, drains this freelist. */
  g_mutex_lock (&callback_deferred_free_lock);
  callback_deferred_free_list = g_list_prepend (callback_deferred_free_list, closure);
  g_mutex_unlock (&callback_deferred_free_lock);
}

void
pygi_callback_closure_drain_deferred_frees (void)
{
  g_mutex_lock (&callback_deferred_free_lock);
  GList *closures = callback_deferred_free_list;
  callback_deferred_free_list = NULL;
  g_mutex_unlock (&callback_deferred_free_lock);

  for (GList *l = closures; l != NULL; l = l->next)
    callback_closure_free ((PyGICallbackClosure *)l->data);
  g_list_free (closures);
}

/**
 * callback_write_direct_value:
 * @value: Python value returned by the callback
 * @type_info: GI metadata for the return or out parameter, or %NULL
 * @tag: fallback GI tag when @type_info is unavailable
 * @transfer: ownership transfer for the callback slot
 * @dst: raw callback return or out-parameter storage
 *
 * Marshals callback scalar/direct-storage values into @dst using the
 * shared memory-target marshaller. Callback-specific pointer/object cases
 * are handled by callback_write_value() before this fallback is reached.
 */
static int
callback_write_direct_value (PyObject *value,
                             GITypeInfo *type_info,
                             GITypeTag tag,
                             GITransfer transfer,
                             void *dst)
{
  if (dst == NULL)
    return 0;
  if (tag == GI_TYPE_TAG_VOID)
    return 0;

  PyGIType type = { 0 };
  if (type_info != NULL)
    {
      if (pygi_type_from_gi (type_info, &type) != 0)
        return 0;
    }
  else if (pygi_type_from_gi_tag (tag, tag == GI_TYPE_TAG_VOID, &type) != 0)
    return 0;

  if (!pygi_type_is_direct_storage (&type))
    return 0;

  return pygi_marshal_from_py (value,
                               &(PyGIMarshalSlot){
                                   .type = type_info,
                                   .pygi_type = &type,
                                   .transfer = transfer,
                                   .transfer_set = true,
                                   .kind = PYGI_MARSHAL_TARGET_MEMORY,
                                   .target.memory = dst,
                               });
}

/**
 * callback_write_default_value:
 * @type_info: GI metadata for the callback return slot, or %NULL
 * @tag: fallback GI tag when @type_info is unavailable
 * @dst: raw callback return storage to initialize
 *
 * Writes the C-level default value used when a Python callback raises.
 * Direct-storage slots are zeroed by resolved storage size; pointer-like
 * unsupported slots fall back to %NULL.
 */
static void
callback_write_default_value (GITypeInfo *type_info, GITypeTag tag, void *dst)
{
  if (dst == NULL)
    return;
  if (tag == GI_TYPE_TAG_VOID)
    return;

  PyGIType type = { 0 };
  if (type_info != NULL && pygi_type_from_gi (type_info, &type) == 0)
    {
      gsize size = pygi_type_storage_size (&type);
      if (size != 0)
        {
          memset (dst, 0, size);
          return;
        }
    }

  if (type_info == NULL && pygi_type_from_gi_tag (tag, tag == GI_TYPE_TAG_VOID, &type) == 0)
    {
      gsize size = pygi_type_storage_size (&type);
      if (size != 0)
        {
          memset (dst, 0, size);
          return;
        }
    }

  *(gpointer *)dst = NULL;
}

static int
callback_write_value (PyObject *value,
                      GITypeInfo *type_info,
                      GITypeTag tag,
                      GITransfer transfer,
                      void *dst)
{
  if (tag == GI_TYPE_TAG_UTF8 || tag == GI_TYPE_TAG_FILENAME)
    {
      if (value == Py_None)
        {
          *(gpointer *)dst = NULL;
          return 0;
        }
      const char *s = NULL;
      PyObject *bytes = NULL;
      if (PyUnicode_Check (value))
        s = PyUnicode_AsUTF8 (value);
      else
        {
          bytes = PyBytes_FromObject (value);
          if (bytes != NULL)
            s = PyBytes_AsString (bytes);
        }
      if (s == NULL)
        {
          Py_XDECREF (bytes);
          return -1;
        }
      *(gpointer *)dst = g_strdup (s);
      Py_XDECREF (bytes);
      return 0;
    }

  if (tag == GI_TYPE_TAG_VOID)
    {
      /* Opaque OUT slot: write the Python int as a raw pointer value,
       * or NULL for None. The closure (or caller) is responsible for
       * interpreting it. */
      if (value == Py_None)
        {
          *(gpointer *)dst = NULL;
          return 0;
        }
      if (PyLong_Check (value))
        {
          *(gpointer *)dst = PyLong_AsVoidPtr (value);
          return PyErr_Occurred () ? -1 : 0;
        }
      *(gpointer *)dst = NULL;
      return 0;
    }
  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
      if (iface != NULL && gi_base_info_is_named (iface, "GObject", "Closure"))
        {
          if (value == Py_None)
            {
              *(gpointer *)dst = NULL;
              return 0;
            }
          if (!PyCallable_Check (value))
            {
              PyErr_SetString (PyExc_TypeError, "GClosure return must be callable or None");
              return -1;
            }
          *(gpointer *)dst = pygi_closure_new (value);
          return *(gpointer *)dst != NULL ? 0 : -1;
        }
      if (iface != NULL && GI_IS_CALLBACK_INFO (iface))
        {
          /* OUT callback slot (e.g. DestroyNotify*): only None → NULL
           * is supported; arbitrary Python callables would require a
           * new ffi closure with no place to keep it alive. */
          *(gpointer *)dst = NULL;
          return 0;
        }
      if (iface != NULL && (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)))
        {
          if (value == Py_None)
            {
              *(gpointer *)dst = NULL;
              return 0;
            }
          GObject *object = pygi_gobject_get (value);
          if (object == NULL)
            return -1;
          /* Refcount accounting for vfunc/callback object returns:
           *   transfer-full: callee consumes a ref — always bump.
           *   transfer-none + wrapper has other Python holders: wrapper
           *     stays alive past the trampoline, so its GObject ref is
           *     enough; no bump (pygobject test_..._with_held_object
           *     asserts grefcount == 1).
           *   transfer-none + wrapper is our only ref: trampoline's
           *     final Py_DECREF will free the wrapper, which unrefs
           *     the GObject. Bump now so the C caller doesn't deref a
           *     freed pointer. Pygobject warns about the leak; we
           *     don't yet. */
          if (G_IS_OBJECT (object))
            {
              if (transfer == GI_TRANSFER_EVERYTHING || Py_REFCNT (value) <= 1)
                g_object_ref (object);
            }
          *(gpointer *)dst = object;
          return 0;
        }
      if (iface != NULL && (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)))
        {
          long long v = PyLong_AsLongLong (value);
          if (v == -1 && PyErr_Occurred ())
            return -1;
          *(int *)dst = (int)v;
          return 0;
        }
      if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
        {
          if (value == Py_None)
            {
              *(gpointer *)dst = NULL;
              return 0;
            }
          gpointer ptr = NULL;
          if (pygi_boxed_get (value, &ptr) != 0)
            return -1;
          *(gpointer *)dst = ptr;
          return 0;
        }
    }
  return callback_write_direct_value (value, type_info, tag, transfer, dst);
}

static PyObject *
callback_result_item (PyObject *result, int index, int total)
{
  if (total == 1)
    return result;
  if (PyTuple_Check (result) && PyTuple_GET_SIZE (result) == total)
    return PyTuple_GET_ITEM (result, index);
  return Py_None;
}

static int
callback_visible_arg_count (PyGICallbackClosure *closure, gboolean include_array_lengths)
{
  int count = 0;
  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      if (arg->direction == GI_DIRECTION_OUT)
        continue;
      if (arg->length_owner_array >= 0 && !include_array_lengths)
        continue;
      count++;
    }
  return count;
}

static int
callback_length_from_arg (void **args, PyGICallbackArgPlan *length_arg, int index)
{
  if (length_arg->direction == GI_DIRECTION_IN)
    {
      if (length_arg->tag == GI_TYPE_TAG_UINT64 || length_arg->tag == GI_TYPE_TAG_GTYPE)
        return (int)*(uint64_t *)args[index];
      if (length_arg->tag == GI_TYPE_TAG_INT64)
        return (int)*(int64_t *)args[index];
      if (length_arg->tag == GI_TYPE_TAG_UINT32)
        return (int)*(uint32_t *)args[index];
      return (int)*(int32_t *)args[index];
    }
  void *slot = *(void **)args[index];
  if (slot == NULL)
    return 0;
  if (length_arg->tag == GI_TYPE_TAG_UINT64 || length_arg->tag == GI_TYPE_TAG_GTYPE)
    return (int)*(uint64_t *)slot;
  if (length_arg->tag == GI_TYPE_TAG_INT64)
    return (int)*(int64_t *)slot;
  if (length_arg->tag == GI_TYPE_TAG_UINT32)
    return (int)*(uint32_t *)slot;
  return (int)*(int32_t *)slot;
}

static void
callback_set_length_arg (void **args, PyGICallbackArgPlan *length_arg, int index, int length)
{
  void *slot = length_arg->direction == GI_DIRECTION_IN ? args[index] : *(void **)args[index];
  if (slot == NULL)
    return;
  if (length_arg->tag == GI_TYPE_TAG_UINT64 || length_arg->tag == GI_TYPE_TAG_GTYPE)
    *(uint64_t *)slot = (uint64_t)length;
  else if (length_arg->tag == GI_TYPE_TAG_INT64)
    *(int64_t *)slot = (int64_t)length;
  else if (length_arg->tag == GI_TYPE_TAG_UINT32)
    *(uint32_t *)slot = (uint32_t)length;
  else
    *(int32_t *)slot = (int32_t)length;
}

static PyObject *
callback_array_to_py (PyGICallbackClosure *closure,
                      PyGICallbackArgPlan *arg,
                      void **args,
                      int index)
{
  void *base
      = arg->direction == GI_DIRECTION_IN ? *(void **)args[index] : *(void **)*(void **)args[index];
  if (arg->array_length_arg < 0)
    {
      if (gi_type_info_is_zero_terminated (arg->type_info)
          && (arg->array_elem_tag == GI_TYPE_TAG_UTF8
              || arg->array_elem_tag == GI_TYPE_TAG_FILENAME))
        return pygi_strv_to_py_list ((gchar **)base, GI_TRANSFER_NOTHING);
      return NULL;
    }

  PyGICallbackArgPlan *length_arg = &closure->args[arg->array_length_arg];
  int length = callback_length_from_arg (args, length_arg, arg->array_length_arg);
  if (length < 0)
    length = 0;
  PyObject *list = PyList_New ((Py_ssize_t)length);
  if (list == NULL)
    return NULL;
  if (base == NULL)
    return list;
  for (int i = 0; i < length; i++)
    {
      PyObject *item = NULL;
      if (arg->array_elem_tag == GI_TYPE_TAG_INT32)
        item = PyLong_FromLong (((int32_t *)base)[i]);
      else if (arg->array_elem_tag == GI_TYPE_TAG_UTF8
               || arg->array_elem_tag == GI_TYPE_TAG_FILENAME)
        item = PyUnicode_FromString (((const char **)base)[i]);
      else if (arg->array_elem_tag == GI_TYPE_TAG_INTERFACE)
        {
          GIArgument item_arg = { 0 };
          if (gi_type_info_is_pointer (arg->array_elem_info))
            {
              item_arg.v_pointer = ((gpointer *)base)[i];
            }
          else
            {
              gsize elem_size = gi_type_info_array_element_size (arg->array_elem_info);
              if (elem_size == 0)
                {
                  Py_DECREF (list);
                  PyErr_SetString (PyExc_NotImplementedError,
                                   "callback array interface element size missing");
                  return NULL;
                }
              item_arg.v_pointer = (char *)base + (gsize)i * elem_size;
            }
          item = pygi_argument_to_py_transfer (closure->callback_info,
                                               arg->array_elem_info,
                                               &item_arg,
                                               arg->transfer);
        }
      else
        item = Py_NewRef (Py_None);
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, i, item);
    }
  return list;
}

static int
callback_array_from_py (PyObject *value,
                        PyGICallbackClosure *closure,
                        PyGICallbackArgPlan *arg,
                        void **args,
                        int index)
{
  GITypeTag etag = arg->array_elem_tag;
  if (etag != GI_TYPE_TAG_INT32 && etag != GI_TYPE_TAG_UINT32 && etag != GI_TYPE_TAG_UTF8
      && etag != GI_TYPE_TAG_FILENAME)
    return 0;
  gboolean is_string = etag == GI_TYPE_TAG_UTF8 || etag == GI_TYPE_TAG_FILENAME;
  if (arg->array_length_arg < 0 && !is_string)
    return 0;
  PyObject *seq = PySequence_Fast (value, "expected a sequence");
  if (seq == NULL)
    return -1;
  Py_ssize_t length = PySequence_Fast_GET_SIZE (seq);
  void *items = NULL;
  if (etag == GI_TYPE_TAG_INT32)
    {
      int32_t *buf = g_new0 (int32_t, (gsize)(length > 0 ? length : 1));
      for (Py_ssize_t i = 0; i < length; i++)
        {
          long v = PyLong_AsLong (PySequence_Fast_GET_ITEM (seq, i));
          if (v == -1 && PyErr_Occurred ())
            {
              Py_DECREF (seq);
              g_free (buf);
              return -1;
            }
          buf[i] = (int32_t)v;
        }
      items = buf;
    }
  else if (etag == GI_TYPE_TAG_UINT32)
    {
      uint32_t *buf = g_new0 (uint32_t, (gsize)(length > 0 ? length : 1));
      for (Py_ssize_t i = 0; i < length; i++)
        {
          unsigned long v = PyLong_AsUnsignedLong (PySequence_Fast_GET_ITEM (seq, i));
          if (v == (unsigned long)-1 && PyErr_Occurred ())
            {
              Py_DECREF (seq);
              g_free (buf);
              return -1;
            }
          buf[i] = (uint32_t)v;
        }
      items = buf;
    }
  else /* utf8 / filename */
    {
      /* NULL-terminated strv; size is length+1. */
      char **buf = g_new0 (char *, (gsize)(length + 1));
      for (Py_ssize_t i = 0; i < length; i++)
        {
          PyObject *item = PySequence_Fast_GET_ITEM (seq, i);
          if (item == Py_None)
            continue;
          const char *s = PyUnicode_AsUTF8 (item);
          if (s == NULL)
            {
              Py_DECREF (seq);
              g_strfreev (buf);
              return -1;
            }
          buf[i] = g_strdup (s);
        }
      items = buf;
    }
  Py_DECREF (seq);
  void **slot = *(void ***)args[index];
  if (arg->direction == GI_DIRECTION_INOUT && slot != NULL && *slot != NULL)
    {
      if (is_string)
        g_strfreev ((char **)*slot);
      else
        g_free (*slot);
    }
  if (slot != NULL)
    *slot = items;
  if (arg->array_length_arg >= 0)
    {
      PyGICallbackArgPlan *length_arg = &closure->args[arg->array_length_arg];
      callback_set_length_arg (args, length_arg, arg->array_length_arg, (int)length);
    }
  return 0;
}

static PyObject *
callback_arg_to_py (PyGICallbackClosure *closure,
                    PyGICallbackArgPlan *arg,
                    void **args,
                    int arg_index,
                    void *src)
{
  (void)arg_index;
  GIArgument aligned = { 0 };
  if (src != NULL)
    {
      switch (gi_type_info_storage_tag (arg->type_info))
        {
#define PYGI_SCALAR PYGI_SCALAR_LOAD_ALIGNED_FROM_SRC

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

        case GI_TYPE_TAG_UTF8:
        case GI_TYPE_TAG_FILENAME:
          aligned.v_string = *(char **)src;
          break;
        default:
          aligned.v_pointer = *(void **)src;
          break;
        }
    }

  if (arg->tag == GI_TYPE_TAG_VOID)
    {
      if (aligned.v_pointer == NULL)
        Py_RETURN_NONE;
      if (arg->wrapper_gtype != 0)
        return pygi_gobject_to_py_as_gtype ((GObject *)aligned.v_pointer,
                                            arg->wrapper_gtype,
                                            GI_TRANSFER_NOTHING);
      return PyLong_FromVoidPtr (aligned.v_pointer);
    }

  if (arg->tag == GI_TYPE_TAG_INTERFACE && aligned.v_pointer != NULL)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (arg->type_info);
      if (iface != NULL && GI_IS_CALLBACK_INFO (iface))
        {
          gpointer user_data_ptr = NULL;
          unsigned int closure_index = 0;
          if (gi_arg_info_get_closure_index (arg->arg_info, &closure_index)
              && closure_index < (unsigned int)closure->n_args)
            {
              PyGICallbackArgPlan *closure_arg = &closure->args[closure_index];
              void *user_data_src = args[closure_index];
              if (closure_arg->direction == GI_DIRECTION_INOUT && user_data_src != NULL)
                user_data_src = *(void **)user_data_src;
              if (user_data_src != NULL)
                user_data_ptr = *(gpointer *)user_data_src;
            }
          return reverse_callback_new (closure->namespace,
                                       (GICallableInfo *)iface,
                                       aligned.v_pointer,
                                       user_data_ptr);
        }
    }

  if (arg->tag == GI_TYPE_TAG_INTERFACE && arg->transfer == GI_TRANSFER_NOTHING
      && aligned.v_pointer != NULL)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (arg->type_info);
      if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
        {
          const char *namespace_name = gi_base_info_get_namespace (iface);
          GType iface_gt = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
          if (iface_gt != G_TYPE_NONE && iface_gt != 0 && G_TYPE_IS_BOXED (iface_gt)
              && g_strcmp0 (namespace_name, "Gst") == 0)
            {
              PyObject *cls = pygi_class_registry_get_pytype_for_gtype (iface_gt);
              if (cls != NULL)
                return pygi_boxed_new_alias (cls, aligned.v_pointer, iface_gt, NULL);
            }
        }
    }

  return pygi_argument_to_py_transfer (closure->callback_info,
                                       arg->type_info,
                                       &aligned,
                                       arg->transfer);
}

static void
callback_trampoline (ffi_cif *cif, void *ret, void **args, void *user_data)
{
  (void)cif;
  PyGICallbackClosure *closure = user_data;
  gboolean defer_async_free = closure->scope == GI_SCOPE_TYPE_ASYNC;
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *previous_namespace = NULL;
  if (pygi_enum_push_namespace_context (closure->namespace, &previous_namespace) != 0)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return;
    }
  /* PyGObject convention: when method.py packs multiple trailing
   * positional args into a `ginext.method._PackedUserData` tuple, the
   * trampoline unpacks them into separate callback positional args. A
   * user-supplied tuple (single positional or user_data= kwarg) stays
   * intact. Size py_args for the worst case so the unpack is in-place. */
  size_t n_py_alloc = (size_t)(closure->n_args > 0 ? closure->n_args : 1);
  gboolean unpack_user_data = FALSE;
  if (closure->py_user_data != NULL && Py_TYPE (closure->py_user_data) != &PyTuple_Type
      && PyTuple_Check (closure->py_user_data))
    {
      /* Subclass-of-tuple: only the private _PackedUserData marker
       * fits the role. Importing the type once is cheap; cache via a
       * static guarded by the closure's first sighting. */
      static PyObject *packed_type = NULL;
      if (packed_type == NULL)
        {
          PyObject *mod = PyImport_ImportModule ("ginext.method");
          if (mod != NULL)
            {
              packed_type = PyObject_GetAttrString (mod, "_PackedUserData");
              Py_DECREF (mod);
            }
          if (packed_type == NULL)
            PyErr_Clear ();
        }
      if (packed_type != NULL
          && PyObject_TypeCheck (closure->py_user_data, (PyTypeObject *)packed_type))
        {
          unpack_user_data = TRUE;
          Py_ssize_t n_extra = PyTuple_GET_SIZE (closure->py_user_data);
          if (n_extra > 0)
            n_py_alloc += (size_t)n_extra;
        }
    }
  PyObject **py_args = g_new0 (PyObject *, n_py_alloc);
  Py_ssize_t n_py_args = 0;
#define APPEND_PY_ARG(obj)                                                                         \
  do                                                                                               \
    {                                                                                              \
      if ((size_t)n_py_args == n_py_alloc)                                                         \
        {                                                                                          \
          n_py_alloc = n_py_alloc > 0 ? n_py_alloc * 2 : 4;                                        \
          py_args = g_renew (PyObject *, py_args, n_py_alloc);                                     \
        }                                                                                          \
      py_args[n_py_args++] = (obj);                                                                \
    }                                                                                              \
  while (0)
  gboolean expose_array_lengths
      = closure->include_array_length_args || closure->callable_arity < 0
        || closure->callable_arity >= callback_visible_arg_count (closure, TRUE);
  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      if (arg->direction == GI_DIRECTION_OUT)
        continue;
      if (arg->length_owner_array >= 0 && !expose_array_lengths)
        continue;
      if (arg->is_closure
          || (closure->py_user_data == NULL && callback_arg_is_trailing_user_data (closure, i)))
        {
          if (closure->py_user_data != NULL)
            {
              if (unpack_user_data)
                {
                  Py_ssize_t n = PyTuple_GET_SIZE (closure->py_user_data);
                  for (Py_ssize_t k = 0; k < n; k++)
                    APPEND_PY_ARG (Py_NewRef (PyTuple_GET_ITEM (closure->py_user_data, k)));
                }
              else
                APPEND_PY_ARG (Py_NewRef (closure->py_user_data));
            }
          else
            {
              /* A truly omitted closure cookie is hidden from Python.
               * Keep the PyGObject convenience where a fixed-arity
               * callable that explicitly declares the slot can still
               * receive None, but do not leak the slot to variadic
               * callbacks such as `lambda *args: ...`. */
              if (closure->callable_arity >= 0 && closure->callable_arity > n_py_args)
                APPEND_PY_ARG (Py_NewRef (Py_None));
            }
          continue;
        }
      void *src = args[i];
      if (arg->direction == GI_DIRECTION_INOUT)
        src = *(void **)args[i];
      PyObject *py = NULL;
      if (arg->tag == GI_TYPE_TAG_ARRAY)
        py = callback_array_to_py (closure, arg, args, i);
      else
        py = callback_arg_to_py (closure, arg, args, i, src);
      if (py == NULL)
        {
          PyErr_Clear ();
          py = Py_NewRef (Py_None);
        }
      APPEND_PY_ARG (py);
    }
#undef APPEND_PY_ARG

  /* CPython asserts no pending error on entry to PyObject_Vectorcall's
   * frame-init path. If a conversion above smuggled one through, clear
   * it before calling — the failure has already been substituted with
   * None, so the callback can still run. */
  if (PyErr_Occurred ())
    PyErr_Clear ();
  /* Trim trailing args if the callable's positional arity is shorter
   * than the GIR-declared callback signature. Lets `def cb():` bind
   * to a `void cb(gpointer user_data)` GIR shape without TypeError. */
  if (closure->callable_arity >= 0 && (Py_ssize_t)closure->callable_arity < n_py_args)
    {
      for (Py_ssize_t k = (Py_ssize_t)closure->callable_arity; k < n_py_args; k++)
        Py_DECREF (py_args[k]);
      n_py_args = (Py_ssize_t)closure->callable_arity;
    }
  PyObject *result = PyObject_Vectorcall (closure->callable, py_args, (size_t)n_py_args, NULL);
  for (Py_ssize_t i = 0; i < n_py_args; i++)
    Py_DECREF (py_args[i]);
  if (result == NULL)
    {
      PyErr_Print ();
      callback_write_default_value (closure->return_type, closure->return_tag, ret);
      g_free (py_args);
      if (defer_async_free)
        callback_closure_release_py_refs (closure);
      pygi_enum_pop_namespace_context (previous_namespace);
      PyGILState_Release (state);
      if (defer_async_free)
        callback_closure_enqueue_deferred_free (closure);
      return;
    }

  gboolean has_return = closure->return_tag != GI_TYPE_TAG_VOID;
  int total_values = closure->n_out_args + (has_return ? 1 : 0);
  int value_index = 0;
  if (has_return)
    {
      PyObject *ret_value = callback_result_item (result, value_index, total_values);
      if (callback_write_value (ret_value,
                                closure->return_type,
                                closure->return_tag,
                                closure->return_transfer,
                                ret)
          != 0)
        PyErr_Print ();
      else if ((closure->return_tag == GI_TYPE_TAG_UTF8
                || closure->return_tag == GI_TYPE_TAG_FILENAME)
               && closure->return_transfer == GI_TRANSFER_NOTHING)
        {
          /* The caller won't free this string; pin it on the closure
           * so it survives this return but is reclaimed on the next
           * call or teardown. */
          g_clear_pointer (&closure->pinned_return, g_free);
          closure->pinned_return = *(char **)ret;
        }
      value_index++;
    }
  else
    callback_write_direct_value (Py_None,
                                 closure->return_type,
                                 closure->return_tag,
                                 closure->return_transfer,
                                 ret);

  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      if (arg->direction == GI_DIRECTION_IN)
        continue;
      if (arg->length_owner_array >= 0)
        continue;
      void *slot = *(void **)args[i];
      PyObject *out_value = callback_result_item (result, value_index, total_values);
      if (arg->tag == GI_TYPE_TAG_ARRAY && total_values == 1 && arg->array_length_arg >= 0
          && PyTuple_Check (result) && PyTuple_GET_SIZE (result) == 2)
        {
          PyObject *array_value = PyTuple_GET_ITEM (result, 0);
          if (PySequence_Check (array_value) && !PyUnicode_Check (array_value)
              && !PyBytes_Check (array_value) && !PyByteArray_Check (array_value))
            out_value = array_value;
        }
      if (arg->tag == GI_TYPE_TAG_ARRAY)
        {
          if (callback_array_from_py (out_value, closure, arg, args, i) != 0)
            PyErr_Print ();
        }
      else if (callback_write_value (out_value, arg->type_info, arg->tag, arg->transfer, slot) != 0)
        PyErr_Print ();
      value_index++;
    }
  Py_DECREF (result);
  g_free (py_args);
  if (defer_async_free)
    callback_closure_release_py_refs (closure);
  pygi_enum_pop_namespace_context (previous_namespace);
  PyGILState_Release (state);
  if (defer_async_free)
    callback_closure_enqueue_deferred_free (closure);
}

void
pygi_callback_closure_destroy (gpointer closure)
{
  /* GLib destroy-notify can run from C with the GIL released (e.g. while a
   * GMainLoop is polling). The closure owns Python references, so always
   * reacquire before freeing it. */
  PyGILState_STATE state = PyGILState_Ensure ();
  callback_closure_free ((PyGICallbackClosure *)closure);
  PyGILState_Release (state);
}

void
pygi_callback_closure_set_py_user_data (gpointer closure, PyObject *user_data)
{
  PyGICallbackClosure *cb = closure;
  if (cb == NULL)
    return;
  Py_XDECREF (cb->py_user_data);
  cb->py_user_data = Py_XNewRef (user_data);
}

int
pygi_callback_closure_new (PyObject *callable,
                           GIBaseInfo *callback_info,
                           GIScopeType scope,
                           GIArgument *dest,
                           PyGIArgCleanup *cleanup)
{
  pygi_callback_closure_drain_deferred_frees ();

  if (callable == Py_None)
    {
      dest->v_pointer = NULL;
      cleanup->kind = PYGI_ARG_CLEANUP_NONE;
      return 0;
    }
  if (!PyCallable_Check (callable))
    {
      PyErr_SetString (PyExc_TypeError, "callback argument must be callable or None");
      return -1;
    }
  PyGICallbackClosure *closure = callback_closure_alloc (callable, (GICallableInfo *)callback_info);
  closure->scope = scope;
  if (ffi_prep_cif (&closure->cif,
                    FFI_DEFAULT_ABI,
                    (unsigned)closure->n_args,
                    closure->ffi_return_type,
                    closure->ffi_arg_types)
      != FFI_OK)
    {
      callback_closure_free (closure);
      PyErr_SetString (PyExc_RuntimeError, "ffi_prep_cif failed");
      return -1;
    }
  closure->closure = ffi_closure_alloc (sizeof (ffi_closure), &closure->code);
  if (closure->closure == NULL)
    {
      callback_closure_free (closure);
      PyErr_NoMemory ();
      return -1;
    }
  if (ffi_prep_closure_loc (closure->closure,
                            &closure->cif,
                            callback_trampoline,
                            closure,
                            closure->code)
      != FFI_OK)
    {
      callback_closure_free (closure);
      PyErr_SetString (PyExc_RuntimeError, "ffi_prep_closure_loc failed");
      return -1;
    }

  dest->v_pointer = closure->code;
  cleanup->ptr = closure;
  cleanup->kind
      = scope == GI_SCOPE_TYPE_CALL ? PYGI_ARG_CLEANUP_FFI_CLOSURE : PYGI_ARG_CLEANUP_NONE;
  return 0;
}

int
pygi_vfunc_closure_new (PyObject *callable,
                        GIBaseInfo *callback_info,
                        GIArgument *dest,
                        PyGIArgCleanup *cleanup)
{
  return pygi_callback_closure_new (callable, callback_info, GI_SCOPE_TYPE_NOTIFIED, dest, cleanup);
}

/* pygi_closure_new / pygi_closure_new_with_kind / pygi_closure_new_for_signal*
 * live in GObject/Closure-signal.c. pygi_callback_closure_* (for GIR callback
 * args) remain stubbed here pending slice 0c. */

PyObject *
pygi_class_registry_get_pytype_for_gtype (GType gtype)
{
  if (boxed_classes_by_gtype == NULL || gtype == 0)
    return NULL;
  PyObject *profile_name = profile_name_from_context ();
  if (profile_name == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  PyObject *key = boxed_registry_key (gtype, profile_name);
  Py_DECREF (profile_name);
  if (key == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  PyObject *cls = PyDict_GetItemWithError (boxed_classes_by_gtype, key);
  Py_DECREF (key);
  if (cls == NULL && PyErr_Occurred ())
    PyErr_Clear ();
  return cls;
}

PyType_Slot ReverseCallback_slots[] = {
  { Py_tp_dealloc, (void *)reverse_callback_dealloc },
  { Py_tp_call, (void *)reverse_callback_call },
  { Py_tp_repr, (void *)reverse_callback_repr },
  { 0, NULL },
};

PyType_Spec ReverseCallback_spec = {
  .name = "ginext.private._gobject.CallbackWrapper",
  .basicsize = sizeof (PyGIReverseCallback),
  .flags = Py_TPFLAGS_DEFAULT,
  .slots = ReverseCallback_slots,
};

__attribute__ ((weak)) int
pygi_foreign_cairo_from_py (PyObject *value,
                            GIBaseInfo *iface,
                            GITransfer transfer,
                            GIArgument *out)
{
  (void)value;
  (void)iface;
  (void)transfer;
  (void)out;
  return 1;
}

__attribute__ ((weak)) PyObject *
pygi_foreign_cairo_to_py (GIBaseInfo *iface, gpointer pointer, GITransfer transfer)
{
  (void)iface;
  (void)pointer;
  (void)transfer;
  return NULL;
}
PyObject *
pygi_build_struct_class (const char *namespace_name, GIBaseInfo *info)
{
  if (namespace_name == NULL || info == NULL)
    Py_RETURN_NONE;
  const char *name = gi_base_info_get_name (info);
  if (name == NULL)
    Py_RETURN_NONE;

  PyObject *ginext = PyImport_ImportModule ("ginext");
  if (ginext == NULL)
    return NULL;
  PyObject *resolver = PyObject_GetAttrString (ginext, "_class_from_namespace_profile");
  Py_DECREF (ginext);
  if (resolver == NULL)
    return NULL;
  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    {
      Py_DECREF (resolver);
      return NULL;
    }
  PyObject *cls = PyObject_CallFunction (resolver, "Oss", context, namespace_name, name);
  Py_DECREF (resolver);
  return cls;
}

typedef struct
{
  PyObject_HEAD GParamSpec *pspec;
} PyGIParamSpec;

static void
param_spec_dealloc (PyGIParamSpec *self)
{
  if (self->pspec != NULL)
    g_param_spec_unref (self->pspec);
  Py_TYPE (self)->tp_free ((PyObject *)self);
}

static PyObject *
param_spec_repr (PyGIParamSpec *self)
{
  const char *name = self->pspec != NULL ? g_param_spec_get_name (self->pspec) : NULL;
  const char *type_name = self->pspec != NULL ? G_OBJECT_TYPE_NAME (self->pspec) : NULL;
  PyObject *name_obj = name != NULL ? PyUnicode_FromString (name) : Py_NewRef (Py_None);
  if (name_obj == NULL)
    return NULL;
  PyObject *repr = PyUnicode_FromFormat ("<%s name=%R at %p>",
                                         type_name != NULL ? type_name : "GParamSpec",
                                         name_obj,
                                         self->pspec);
  Py_DECREF (name_obj);
  return repr;
}

static PyObject *
param_spec_get_name (PyGIParamSpec *self, void *closure G_GNUC_UNUSED)
{
  const char *name = self->pspec != NULL ? g_param_spec_get_name (self->pspec) : NULL;
  if (name == NULL)
    Py_RETURN_NONE;
  return PyUnicode_FromString (name);
}

static PyObject *
param_spec_get_nick (PyGIParamSpec *self, void *closure G_GNUC_UNUSED)
{
  const char *nick = self->pspec != NULL ? g_param_spec_get_nick (self->pspec) : NULL;
  if (nick == NULL)
    Py_RETURN_NONE;
  return PyUnicode_FromString (nick);
}

static PyObject *
param_spec_get_blurb (PyGIParamSpec *self, void *closure G_GNUC_UNUSED)
{
  const char *blurb = self->pspec != NULL ? g_param_spec_get_blurb (self->pspec) : NULL;
  if (blurb == NULL)
    Py_RETURN_NONE;
  return PyUnicode_FromString (blurb);
}

static PyObject *
param_spec_get_value_type (PyGIParamSpec *self, void *closure G_GNUC_UNUSED)
{
  if (self->pspec == NULL)
    Py_RETURN_NONE;
  /* GType is gsize (pointer-width); unsigned long is only 32-bit on LLP64
     (Windows), which truncates registered-type GTypes. */
  return PyLong_FromUnsignedLongLong ((unsigned long long)self->pspec->value_type);
}

static PyGetSetDef param_spec_getsets[] = {
  { "name", (getter)param_spec_get_name, NULL, NULL, NULL },
  { "nick", (getter)param_spec_get_nick, NULL, NULL, NULL },
  { "blurb", (getter)param_spec_get_blurb, NULL, NULL, NULL },
  { "value_type", (getter)param_spec_get_value_type, NULL, NULL, NULL },
  { NULL, NULL, NULL, NULL, NULL },
};

static PyTypeObject param_spec_type = {
  PyVarObject_HEAD_INIT (NULL, 0).tp_name = "ginext.private.ParamSpec",
  .tp_basicsize = sizeof (PyGIParamSpec),
  .tp_dealloc = (destructor)param_spec_dealloc,
  .tp_repr = (reprfunc)param_spec_repr,
  .tp_getset = param_spec_getsets,
  .tp_flags = Py_TPFLAGS_DEFAULT,
};

PyObject *
pygi_param_spec_new (GParamSpec *pspec)
{
  if (pspec == NULL)
    Py_RETURN_NONE;
  if (PyType_Ready (&param_spec_type) < 0)
    return NULL;
  PyGIParamSpec *self = PyObject_New (PyGIParamSpec, &param_spec_type);
  if (self == NULL)
    return NULL;
  self->pspec = g_param_spec_ref (pspec);
  return (PyObject *)self;
}

int
pygi_param_spec_from_py (PyObject *obj, GParamSpec **out_pspec)
{
  PyObject *repr = NULL;
  if (out_pspec == NULL)
    {
      PyErr_SetString (PyExc_SystemError, "pygi_param_spec_from_py: NULL out pointer");
      return -1;
    }
  *out_pspec = NULL;
  if (obj == Py_None)
    return 0;

  if (PyType_Ready (&param_spec_type) < 0)
    return -1;
  if (!PyObject_TypeCheck (obj, &param_spec_type))
    {
      repr = PyObject_Repr (obj);
      PyErr_Format (PyExc_TypeError,
                    "expected GObject.ParamSpec, got %.200s",
                    repr != NULL ? PyUnicode_AsUTF8 (repr) : Py_TYPE (obj)->tp_name);
      Py_XDECREF (repr);
      return -1;
    }

  *out_pspec = ((PyGIParamSpec *)obj)->pspec;
  return 0;
}

PyObject *
py_param_spec_from_gtype_name (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "Os", &gtype_obj, &name))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  if (gtype == G_TYPE_INVALID || !G_TYPE_IS_OBJECT (gtype))
    Py_RETURN_NONE;

  gpointer klass = g_type_class_ref (gtype);
  if (klass == NULL)
    Py_RETURN_NONE;
  GParamSpec *pspec = g_object_class_find_property (G_OBJECT_CLASS (klass), name);
  PyObject *out = pygi_param_spec_new (pspec);
  g_type_class_unref (klass);
  return out;
}

PyObject *
py_object_class_list_property_names (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &gtype_obj))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  if (gtype == G_TYPE_INVALID || !G_TYPE_IS_OBJECT (gtype))
    return PyList_New (0);

  gpointer klass = g_type_class_ref (gtype);
  if (klass == NULL)
    return PyList_New (0);

  guint n_props = 0;
  GParamSpec **props = g_object_class_list_properties (G_OBJECT_CLASS (klass), &n_props);
  PyObject *result = PyList_New ((Py_ssize_t)n_props);
  if (result == NULL)
    {
      g_free (props);
      g_type_class_unref (klass);
      return NULL;
    }
  for (guint i = 0; i < n_props; i++)
    {
      PyObject *name = PyUnicode_FromString (g_param_spec_get_name (props[i]));
      if (name == NULL)
        {
          Py_DECREF (result);
          g_free (props);
          g_type_class_unref (klass);
          return NULL;
        }
      PyList_SET_ITEM (result, (Py_ssize_t)i, name);
    }
  g_free (props);
  g_type_class_unref (klass);
  return result;
}

PyObject *
py_type_has_value_table (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &gtype_obj))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;

  return PyBool_FromLong (g_type_value_table_peek (gtype) != NULL);
}

PyObject *
py_interface_list_properties (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &gtype_obj))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  if (!G_TYPE_IS_INTERFACE (gtype))
    {
      PyErr_SetString (PyExc_TypeError, "GType is not an interface");
      return NULL;
    }

  gpointer iface = g_type_default_interface_ref (gtype);
  if (iface == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "could not reference interface");
      return NULL;
    }

  guint n_props = 0;
  GParamSpec **props = g_object_interface_list_properties (iface, &n_props);
  PyObject *result = PyList_New (n_props);
  if (result == NULL)
    {
      g_free (props);
      g_type_default_interface_unref (iface);
      return NULL;
    }

  for (guint i = 0; i < n_props; i++)
    {
      PyObject *item = pygi_param_spec_new (props[i]);
      if (item == NULL)
        {
          Py_DECREF (result);
          g_free (props);
          g_type_default_interface_unref (iface);
          return NULL;
        }
      PyList_SET_ITEM (result, i, item);
    }

  g_free (props);
  g_type_default_interface_unref (iface);
  return result;
}


static GParamSpec *
param_spec_from_pointer_arg (PyObject *obj)
{
  if (PyObject_TypeCheck (obj, &param_spec_type))
    {
      PyGIParamSpec *ps = (PyGIParamSpec *)obj;
      if (ps->pspec == NULL)
        {
          PyErr_SetString (PyExc_ValueError, "pspec pointer is NULL");
          return NULL;
        }
      return ps->pspec;
    }
  unsigned long long raw = PyLong_AsUnsignedLongLong (obj);
  if (raw == (unsigned long long)-1 && PyErr_Occurred ())
    return NULL;
  if (raw == 0)
    {
      PyErr_SetString (PyExc_ValueError, "pspec pointer is NULL");
      return NULL;
    }
  return (GParamSpec *)(uintptr_t)raw;
}

PyObject *
py_param_spec_info (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  GParamSpec *pspec = param_spec_from_pointer_arg (ptr_obj);
  if (pspec == NULL)
    return NULL;

  return Py_BuildValue ("{s:K,s:s,s:z,s:z,s:I,s:K,s:z,s:K}",
                        "pointer",
                        (unsigned long long)(uintptr_t)pspec,
                        "name",
                        g_param_spec_get_name (pspec),
                        "nick",
                        g_param_spec_get_nick (pspec),
                        "blurb",
                        g_param_spec_get_blurb (pspec),
                        "flags",
                        (unsigned int)pspec->flags,
                        "value_type",
                        (unsigned long long)pspec->value_type,
                        "value_type_name",
                        g_type_name (pspec->value_type),
                        "owner_type",
                        (unsigned long long)pspec->owner_type);
}

PyObject *
py_param_spec_default_value (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  GParamSpec *pspec = param_spec_from_pointer_arg (ptr_obj);
  if (pspec == NULL)
    return NULL;

  const GValue *value = g_param_spec_get_default_value (pspec);
  if (value == NULL)
    Py_RETURN_NONE;
  return pygi_gvalue_value_to_py ((GValue *)value);
}

static PyObject *
numeric_info_new (PyObject *minimum, PyObject *maximum, PyObject *default_value)
{
  if (minimum == NULL || maximum == NULL || default_value == NULL)
    {
      Py_XDECREF (minimum);
      Py_XDECREF (maximum);
      Py_XDECREF (default_value);
      return NULL;
    }

  PyObject *dict = PyDict_New ();
  if (dict == NULL)
    {
      Py_DECREF (minimum);
      Py_DECREF (maximum);
      Py_DECREF (default_value);
      return NULL;
    }
  if (PyDict_SetItemString (dict, "minimum", minimum) < 0
      || PyDict_SetItemString (dict, "maximum", maximum) < 0
      || PyDict_SetItemString (dict, "default_value", default_value) < 0)
    {
      Py_DECREF (minimum);
      Py_DECREF (maximum);
      Py_DECREF (default_value);
      Py_DECREF (dict);
      return NULL;
    }

  Py_DECREF (minimum);
  Py_DECREF (maximum);
  Py_DECREF (default_value);
  return dict;
}

PyObject *
py_param_spec_numeric_info (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  GParamSpec *pspec = param_spec_from_pointer_arg (ptr_obj);
  if (pspec == NULL)
    return NULL;

  GType value_type = pspec->value_type;
  if (value_type == G_TYPE_CHAR)
    {
      GParamSpecChar *p = G_PARAM_SPEC_CHAR (pspec);
      return numeric_info_new (PyLong_FromLong (p->minimum),
                               PyLong_FromLong (p->maximum),
                               PyLong_FromLong (p->default_value));
    }
  if (value_type == G_TYPE_UCHAR)
    {
      GParamSpecUChar *p = G_PARAM_SPEC_UCHAR (pspec);
      return numeric_info_new (PyLong_FromUnsignedLong (p->minimum),
                               PyLong_FromUnsignedLong (p->maximum),
                               PyLong_FromUnsignedLong (p->default_value));
    }
  if (value_type == G_TYPE_INT)
    {
      GParamSpecInt *p = G_PARAM_SPEC_INT (pspec);
      return numeric_info_new (PyLong_FromLong (p->minimum),
                               PyLong_FromLong (p->maximum),
                               PyLong_FromLong (p->default_value));
    }
  if (value_type == G_TYPE_UINT)
    {
      GParamSpecUInt *p = G_PARAM_SPEC_UINT (pspec);
      return numeric_info_new (PyLong_FromUnsignedLong (p->minimum),
                               PyLong_FromUnsignedLong (p->maximum),
                               PyLong_FromUnsignedLong (p->default_value));
    }
  if (value_type == G_TYPE_LONG)
    {
      GParamSpecLong *p = G_PARAM_SPEC_LONG (pspec);
      return numeric_info_new (PyLong_FromLong (p->minimum),
                               PyLong_FromLong (p->maximum),
                               PyLong_FromLong (p->default_value));
    }
  if (value_type == G_TYPE_ULONG)
    {
      GParamSpecULong *p = G_PARAM_SPEC_ULONG (pspec);
      return numeric_info_new (PyLong_FromUnsignedLong (p->minimum),
                               PyLong_FromUnsignedLong (p->maximum),
                               PyLong_FromUnsignedLong (p->default_value));
    }
  if (value_type == G_TYPE_INT64)
    {
      GParamSpecInt64 *p = G_PARAM_SPEC_INT64 (pspec);
      return numeric_info_new (PyLong_FromLongLong (p->minimum),
                               PyLong_FromLongLong (p->maximum),
                               PyLong_FromLongLong (p->default_value));
    }
  if (value_type == G_TYPE_UINT64)
    {
      GParamSpecUInt64 *p = G_PARAM_SPEC_UINT64 (pspec);
      return numeric_info_new (PyLong_FromUnsignedLongLong (p->minimum),
                               PyLong_FromUnsignedLongLong (p->maximum),
                               PyLong_FromUnsignedLongLong (p->default_value));
    }
  if (value_type == G_TYPE_FLOAT)
    {
      GParamSpecFloat *p = G_PARAM_SPEC_FLOAT (pspec);
      return numeric_info_new (PyFloat_FromDouble (p->minimum),
                               PyFloat_FromDouble (p->maximum),
                               PyFloat_FromDouble (p->default_value));
    }
  if (value_type == G_TYPE_DOUBLE)
    {
      GParamSpecDouble *p = G_PARAM_SPEC_DOUBLE (pspec);
      return numeric_info_new (PyFloat_FromDouble (p->minimum),
                               PyFloat_FromDouble (p->maximum),
                               PyFloat_FromDouble (p->default_value));
    }

  PyErr_Format (PyExc_TypeError,
                "GParamSpec value type %s is not numeric",
                g_type_name (value_type));
  return NULL;
}

GIRepository *
pygi_shared_repository (void)
{
  static GIRepository *default_repo = NULL;
  if (default_repo == NULL)
    default_repo = gi_repository_dup_default ();
  return default_repo;
}

int
pygi_load_array_element (GITypeInfo *elem_ti,
                         const char *base,
                         guint index,
                         gsize elem_size,
                         GIArgument *out)
{
  const char *ptr = base + ((size_t)index * elem_size);
  GITypeTag storage_tag = gi_type_info_storage_tag (elem_ti);
  switch (storage_tag)
    {
#define PYGI_SCALAR PYGI_SCALAR_LOAD_OUT_FROM_PTR

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    default:
      if (gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_UTF8
          || gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_FILENAME)
        {
          out->v_string = *(char *const *)ptr;
          return 0;
        }
      if (gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_ARRAY)
        {
          out->v_pointer = *(void *const *)ptr;
          return 0;
        }
      if (gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_INTERFACE)
        {
          g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_ti);
          if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
              && !gi_type_info_is_pointer (elem_ti))
            out->v_pointer = (void *)ptr;
          else
            out->v_pointer = *(void *const *)ptr;
          return 0;
        }
      return -1;
    }
}
