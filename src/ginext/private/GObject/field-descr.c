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

/* ── Record field descriptors ──────────────────────────────────────────────
 *
 * py_record_install_field_descriptors(cls, info) builds PyGetSetDef-backed
 * "getset_descriptor" entries for fields in a struct/union GI info and
 * installs them on `cls`.  Once installed, a plain attribute lookup
 * (tp_getattro dict walk) finds the descriptor before RecordBase.__getattr__
 * is ever called.
 *
 * Lifetime: the descriptor closure blocks must outlive the descriptors. We
 * keep them alive by storing a PyCapsule under __field_desc_bundle__ on the
 * class dict.
 * ────────────────────────────────────────────────────────────────────────── */

#include "GObject/field-descr.h"
#include "GObject/Boxed.h"
#include "GObject/GIMeta.h"
#include "GIRepository/BaseInfo.h"
#include "gimeta-helpers.h"
#include "marshal/container-element.h"
#include "marshal/scalar.h"
#include "runtime/type-info.h"

#include <girepository/girepository.h>

#define info_from_capsule gi_info_from_py

typedef struct
{
  GIBaseInfo *owner_info;
  GIFieldInfo *field;
  size_t offset;
  char *name;
  PyGetSetDef *def;
} FieldDescriptor;

static gboolean
array_field_to_py_supported (GITypeInfo *fti)
{
  g_autoptr (GITypeInfo) inner_ti = gi_type_info_get_param_type (fti, 0);
  if (inner_ti == NULL)
    return FALSE;

  if (gi_type_info_get_array_type (fti) == GI_ARRAY_TYPE_ARRAY)
    {
      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      return itag == GI_TYPE_TAG_VOID || itag == GI_TYPE_TAG_UINT8;
    }

  if (gi_type_info_get_array_type (fti) != GI_ARRAY_TYPE_C)
    return FALSE;

  if (gi_type_info_is_zero_terminated (fti))
    {
      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      if (itag == GI_TYPE_TAG_UTF8 || itag == GI_TYPE_TAG_FILENAME)
        return TRUE;
      if (itag == GI_TYPE_TAG_INTERFACE)
        return TRUE;
    }

  size_t fixed = 0;
  if (gi_type_info_get_array_fixed_size (fti, &fixed) && fixed > 0)
    {
      PyGIContainerElement element;
      if (pygi_container_element_init (&element, inner_ti) != 0)
        {
          PyErr_Clear ();
          return FALSE;
        }
      return pygi_container_element_inline_size (&element) != 0;
    }

  return FALSE;
}

static gboolean
array_field_from_py_supported (GITypeInfo *fti)
{
  if (gi_type_info_get_array_type (fti) != GI_ARRAY_TYPE_C)
    return FALSE;

  g_autoptr (GITypeInfo) inner_ti = gi_type_info_get_param_type (fti, 0);
  if (inner_ti == NULL)
    return FALSE;

  if (gi_type_info_is_zero_terminated (fti))
    {
      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      if (itag == GI_TYPE_TAG_UTF8 || itag == GI_TYPE_TAG_FILENAME)
        return TRUE;
    }

  size_t fixed = 0;
  if (gi_type_info_get_array_fixed_size (fti, &fixed) && fixed > 0)
    {
      PyGIContainerElement element;
      if (pygi_container_element_init (&element, inner_ti) != 0)
        {
          PyErr_Clear ();
          return FALSE;
        }
      return pygi_container_element_inline_size (&element) != 0;
    }

  return FALSE;
}

gboolean
field_to_py_supported (GITypeInfo *fti)
{
  GITypeTag ftag = gi_type_info_get_tag (fti);
  if (ftag == GI_TYPE_TAG_VOID)
    return TRUE;
  if (ftag == GI_TYPE_TAG_ARRAY)
    return array_field_to_py_supported (fti);
  if (ftag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      return finfo != NULL
             && (GI_IS_ENUM_INFO (finfo) || GI_IS_FLAGS_INFO (finfo)
                 || GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo)
                 || GI_IS_OBJECT_INFO (finfo) || GI_IS_INTERFACE_INFO (finfo));
    }

  PyGIType field_type = { 0 };
  if (pygi_type_from_gi (fti, &field_type) != 0)
    {
      PyErr_Clear ();
      return FALSE;
    }
  return pygi_type_is_direct_storage (&field_type);
}

static gboolean
field_from_py_supported (GITypeInfo *fti)
{
  GITypeTag ftag = gi_type_info_get_tag (fti);
  if (ftag == GI_TYPE_TAG_ARRAY)
    return array_field_from_py_supported (fti);
  if (ftag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo != NULL
          && (GI_IS_ENUM_INFO (finfo) || GI_IS_FLAGS_INFO (finfo)
              || GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo)
              || GI_IS_OBJECT_INFO (finfo) || GI_IS_INTERFACE_INFO (finfo)))
        return TRUE;
    }

  PyGIType field_type = { 0 };
  if (pygi_type_from_gi (fti, &field_type) != 0)
    {
      PyErr_Clear ();
      return FALSE;
    }
  return pygi_type_is_direct_storage (&field_type);
}

static gboolean
field_uses_pointer_value_semantics (GIBaseInfo *owner_info, const char *field_name)
{
  const char *owner_name = gi_base_info_get_name (owner_info);
  if (owner_name == NULL || field_name == NULL)
    return FALSE;

  return strcmp (field_name, "data") == 0
         && (strcmp (owner_name, "List") == 0 || strcmp (owner_name, "SList") == 0);
}

static PyObject *
field_desc_getter (PyObject *self, void *closure)
{
  FieldDescriptor *fdc = (FieldDescriptor *)closure;
  if (!(gi_field_info_get_flags (fdc->field) & GI_FIELD_IS_READABLE))
    {
      PyErr_Format (PyExc_AttributeError, "field %s is not readable", fdc->name);
      return NULL;
    }

  gpointer ptr = NULL;
  if (pygi_boxed_get (self, &ptr) != 0)
    return NULL;
  if (ptr == NULL)
    Py_RETURN_NONE;

  g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (fdc->field);
  if (fti == NULL)
    {
      PyErr_Format (PyExc_NotImplementedError, "field %s: missing type info", fdc->name);
      return NULL;
    }

  if (GI_IS_UNION_INFO (fdc->owner_info)
      && !(gi_field_info_get_flags (fdc->field) & GI_FIELD_IS_WRITABLE)
      && gi_type_info_get_tag (fti) == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo != NULL && (GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo)))
        {
          PyErr_Format (PyExc_AttributeError, "field %s is not readable", fdc->name);
          return NULL;
        }
    }

  if (GI_IS_UNION_INFO (fdc->owner_info)
      && gi_type_info_get_tag (fti) == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo != NULL && (GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo)))
        return union_interface_field_shadow_to_py (fti, (char *)ptr, fdc->offset, self, fdc->name);
    }

  if (gi_type_info_get_tag (fti) == GI_TYPE_TAG_VOID
      && field_uses_pointer_value_semantics (fdc->owner_info, fdc->name))
    return PyLong_FromVoidPtr (*(gpointer *)((char *)ptr + fdc->offset));

  PyObject *out = field_to_py (fti, (char *)ptr, fdc->offset, self);
  if (out == NULL && !PyErr_Occurred ())
    PyErr_Format (PyExc_NotImplementedError, "field %s: marshalling not implemented", fdc->name);
  return out;
}

static int
field_desc_setter (PyObject *self, PyObject *value, void *closure)
{
  if (value == NULL)
    {
      PyErr_SetString (PyExc_AttributeError, "cannot delete struct field");
      return -1;
    }
  FieldDescriptor *fdc = (FieldDescriptor *)closure;
  if (!(gi_field_info_get_flags (fdc->field) & GI_FIELD_IS_WRITABLE))
    {
      PyErr_Format (PyExc_AttributeError, "field %s is not writable", fdc->name);
      return -1;
    }

  gpointer ptr = NULL;
  if (pygi_boxed_get (self, &ptr) != 0)
    return -1;
  if (ptr == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "cannot set field on detached record");
      return -1;
    }

  g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (fdc->field);
  if (fti == NULL)
    {
      PyErr_Format (PyExc_NotImplementedError, "field %s: missing type info", fdc->name);
      return -1;
    }
  if (gi_type_info_get_tag (fti) == GI_TYPE_TAG_VOID
      && field_uses_pointer_value_semantics (fdc->owner_info, fdc->name))
    {
      gpointer *slot = (gpointer *)((char *)ptr + fdc->offset);
      if (value == Py_None)
        {
          *slot = NULL;
          return 0;
        }
      *slot = PyLong_AsVoidPtr (value);
      return PyErr_Occurred () ? -1 : 0;
    }
  return field_from_py (fti, (char *)ptr, fdc->offset, value);
}

static void
field_desc_closure_destroy (gpointer data)
{
  FieldDescriptor *fdc = (FieldDescriptor *)data;
  if (fdc == NULL)
    return;
  if (fdc->owner_info != NULL)
    gi_base_info_unref (fdc->owner_info);
  if (fdc->field != NULL)
    gi_base_info_unref ((GIBaseInfo *)fdc->field);
  if (fdc->def != NULL)
    g_free (fdc->def);
  g_free (fdc->name);
  g_free (fdc);
}

static void
field_desc_bundle_destroy (PyObject *cap)
{
  GPtrArray *arr = (GPtrArray *)PyCapsule_GetPointer (cap, "_ginext_field_desc_bundle");
  if (arr != NULL)
    g_ptr_array_unref (arr);
}

int
record_class_field_name_reserved (PyObject *cls, const char *name)
{
  PyObject *gimeta = NULL;
  if (pygi_object_get_gimeta (cls, &gimeta) < 0)
    return -1;
  if (gimeta == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }

  PyObject *method_infos = NULL;
  if (pygi_gimeta_get_method_infos (gimeta, &method_infos) < 0)
    {
      Py_DECREF (gimeta);
      return -1;
    }
  if (method_infos == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        PyErr_Clear ();
      else
        {
          Py_DECREF (gimeta);
          return -1;
        }
    }
  else
    {
      int contains = PyMapping_HasKeyString (method_infos, name);
      Py_DECREF (method_infos);
      if (contains != 0)
        {
          Py_DECREF (gimeta);
          return contains;
        }
    }

  PyObject *hidden_fields = NULL;
  if (pygi_gimeta_get_hidden_fields (gimeta, &hidden_fields) < 0)
    {
      Py_DECREF (gimeta);
      return -1;
    }
  Py_DECREF (gimeta);
  if (hidden_fields == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }
  PyObject *py_name = PyUnicode_FromString (name);
  if (py_name == NULL)
    {
      Py_DECREF (hidden_fields);
      return -1;
    }
  int contains = PySequence_Contains (hidden_fields, py_name);
  Py_DECREF (py_name);
  Py_DECREF (hidden_fields);
  return contains;
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

  GPtrArray *bundle = g_ptr_array_new_with_free_func (field_desc_closure_destroy);

  int n = gi_struct_or_union_n_fields (info);
  for (int fi = 0; fi < n; fi++)
    {
      g_autoptr (GIFieldInfo) field = (GIFieldInfo *)gi_struct_or_union_get_field (info, (guint)fi);
      if (field == NULL)
        continue;
      GIFieldInfoFlags flags = gi_field_info_get_flags (field);
      if (!(flags & GI_FIELD_IS_READABLE) && !(flags & GI_FIELD_IS_WRITABLE))
        continue;
      g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
      if (fti == NULL)
        continue;
      gboolean can_get = (flags & GI_FIELD_IS_READABLE) && field_to_py_supported (fti);
      gboolean can_set = (flags & GI_FIELD_IS_WRITABLE) && field_from_py_supported (fti);
      if (!can_get && !can_set)
        continue;

      const char *raw_name = gi_base_info_get_name ((GIBaseInfo *)field);
      if (raw_name == NULL)
        continue;
      int reserved = record_class_field_name_reserved (cls, raw_name);
      if (reserved < 0)
        {
          g_ptr_array_unref (bundle);
          return NULL;
        }
      if (reserved)
        continue;

      FieldDescriptor *fdc = g_new0 (FieldDescriptor, 1);
      fdc->owner_info = gi_base_info_ref (info);
      fdc->field = (GIFieldInfo *)gi_base_info_ref ((GIBaseInfo *)field);
      fdc->offset = gi_field_info_get_offset (field);
      fdc->name = g_strdup (raw_name);

      /* PyDescr_NewGetSet stores the PyGetSetDef* by pointer, not by value,
       * so the def must be heap-allocated and outlive the descriptor. */
      PyGetSetDef *def = g_new0 (PyGetSetDef, 1);
      def->name = fdc->name;
      def->get = can_get ? field_desc_getter : NULL;
      def->set = can_set ? field_desc_setter : NULL;
      def->doc = NULL;
      def->closure = (void *)fdc;
      fdc->def = def;

      PyObject *desc = PyDescr_NewGetSet ((PyTypeObject *)cls, def);
      if (desc == NULL)
        {
          field_desc_closure_destroy (fdc);
          g_ptr_array_unref (bundle);
          return NULL;
        }
      int rc = PyDict_SetItemString (((PyTypeObject *)cls)->tp_dict, fdc->name, desc);
      Py_DECREF (desc);
      if (rc != 0)
        {
          field_desc_closure_destroy (fdc);
          g_ptr_array_unref (bundle);
          return NULL;
        }
      g_ptr_array_add (bundle, fdc);
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
