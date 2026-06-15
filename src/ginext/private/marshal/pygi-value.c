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

#include "marshal/pygi-value.h"

#include "marshal/scalar.h"
#include "marshal/string.h"
#include "GObject/Object-info.h"
#include "gimeta-helpers.h"
#include "runtime/type-info.h"

#include <stdint.h>
#include <string.h>

static PyGITypeKind
pygi_type_kind_from_gi_tag (GITypeTag tag, bool is_pointer)
{
  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      return is_pointer ? PYGI_TYPE_POINTER : PYGI_TYPE_VOID;
#define PYGI_SCALAR PYGI_SCALAR_RETURN_PYGI_TYPE_KIND

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case GI_TYPE_TAG_UTF8:
      return PYGI_TYPE_UTF8;
    case GI_TYPE_TAG_FILENAME:
      return PYGI_TYPE_FILENAME;
    case GI_TYPE_TAG_INTERFACE:
      return PYGI_TYPE_INTERFACE;
    case GI_TYPE_TAG_ARRAY:
      return PYGI_TYPE_ARRAY;
    case GI_TYPE_TAG_GLIST:
      return PYGI_TYPE_GLIST;
    case GI_TYPE_TAG_GSLIST:
      return PYGI_TYPE_GSLIST;
    case GI_TYPE_TAG_GHASH:
      return PYGI_TYPE_GHASH;
    case GI_TYPE_TAG_ERROR:
      return PYGI_TYPE_ERROR;
    default:
      return PYGI_TYPE_UNSUPPORTED;
    }
}

int
pygi_type_from_gi_tag (GITypeTag tag, bool is_pointer, PyGIType *out)
{
  g_return_val_if_fail (out != NULL, -1);

  *out = (PyGIType){
    .kind = pygi_type_kind_from_gi_tag (tag, is_pointer),
    .gi_tag = tag,
    .transfer = GI_TRANSFER_NOTHING,
    .gtype = G_TYPE_INVALID,
    .is_pointer = is_pointer,
  };
  return out->kind == PYGI_TYPE_UNSUPPORTED ? -1 : 0;
}

int
pygi_type_from_gi (GITypeInfo *ti, PyGIType *out)
{
  g_return_val_if_fail (ti != NULL, -1);
  GITypeTag tag = gi_type_info_get_tag (ti);
  int rc = pygi_type_from_gi_tag (tag, gi_type_info_is_pointer (ti), out);
  if (rc != 0 || tag != GI_TYPE_TAG_INTERFACE)
    return rc;

  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL)
    return 0;
  if (GI_IS_OBJECT_INFO (iface))
    out->kind = PYGI_TYPE_OBJECT;
  else if (GI_IS_INTERFACE_INFO (iface))
    out->kind = PYGI_TYPE_INTERFACE;
  /* Flags before enum: GIFlagsInfo is a subtype of GIEnumInfo. */
  else if (GI_IS_FLAGS_INFO (iface))
    out->kind = PYGI_TYPE_FLAGS;
  else if (GI_IS_ENUM_INFO (iface))
    out->kind = PYGI_TYPE_ENUM;
  else if (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
    out->kind = PYGI_TYPE_BOXED;
  else if (GI_IS_CALLBACK_INFO (iface))
    out->kind = PYGI_TYPE_CALLBACK;
  /* Cache the registered GType for interfaces that carry one. bind.c
   * reads this to type-check Python args (e.g. rejecting a bare GObject
   * where a GIMarshallingTests.Object subclass is required). Skip
   * callbacks - those don't have a meaningful GType for arg checking. */
  if (GI_IS_REGISTERED_TYPE_INFO (iface) && !GI_IS_CALLBACK_INFO (iface))
    out->gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
  return 0;
}

int
pygi_type_from_gtype (GType gtype, PyGIType *out)
{
  g_return_val_if_fail (out != NULL, -1);

  PyGITypeKind kind = PYGI_TYPE_UNSUPPORTED;
  if (gtype == G_TYPE_GTYPE)
    kind = PYGI_TYPE_GTYPE;
  else
    {
      switch (G_TYPE_FUNDAMENTAL (gtype))
        {
        case G_TYPE_BOOLEAN:
          kind = PYGI_TYPE_BOOLEAN;
          break;
        case G_TYPE_CHAR:
          kind = PYGI_TYPE_INT8;
          break;
        case G_TYPE_UCHAR:
          kind = PYGI_TYPE_UINT8;
          break;
        case G_TYPE_INT:
          kind = PYGI_TYPE_INT32;
          break;
        case G_TYPE_UINT:
          kind = PYGI_TYPE_UINT32;
          break;
        case G_TYPE_LONG:
        case G_TYPE_INT64:
          kind = PYGI_TYPE_INT64;
          break;
        case G_TYPE_ULONG:
        case G_TYPE_UINT64:
          kind = PYGI_TYPE_UINT64;
          break;
        case G_TYPE_FLOAT:
          kind = PYGI_TYPE_FLOAT;
          break;
        case G_TYPE_DOUBLE:
          kind = PYGI_TYPE_DOUBLE;
          break;
        case G_TYPE_STRING:
          kind = PYGI_TYPE_UTF8;
          break;
        case G_TYPE_POINTER:
          kind = PYGI_TYPE_POINTER;
          break;
        case G_TYPE_OBJECT:
          kind = PYGI_TYPE_OBJECT;
          break;
        case G_TYPE_INTERFACE:
          kind = PYGI_TYPE_INTERFACE;
          break;
        case G_TYPE_BOXED:
          kind = PYGI_TYPE_BOXED;
          break;
        case G_TYPE_ENUM:
          kind = PYGI_TYPE_ENUM;
          break;
        case G_TYPE_FLAGS:
          kind = PYGI_TYPE_FLAGS;
          break;
        case G_TYPE_VARIANT:
          kind = PYGI_TYPE_VARIANT;
          break;
        default:
          break;
        }
    }

  *out = (PyGIType){
    .kind = kind,
    .gi_tag = GI_TYPE_TAG_VOID,
    .transfer = GI_TRANSFER_NOTHING,
    .gtype = gtype,
    .is_pointer = kind == PYGI_TYPE_POINTER || kind == PYGI_TYPE_INTERFACE,
  };
  return kind == PYGI_TYPE_UNSUPPORTED ? -1 : 0;
}

int
pygi_type_from_gvalue (const GValue *value, PyGIType *out)
{
  g_return_val_if_fail (value != NULL, -1);
  return pygi_type_from_gtype (G_VALUE_TYPE (value), out);
}

static bool
pygi_type_storage_tag (const PyGIType *type, GITypeTag *out)
{
  g_return_val_if_fail (out != NULL, false);

  if (type == NULL)
    return false;

  switch (type->kind)
    {
    case PYGI_TYPE_VOID:
    case PYGI_TYPE_POINTER:
      *out = GI_TYPE_TAG_VOID;
      return true;
#define PYGI_SCALAR PYGI_SCALAR_SET_GI_TYPE_TAG

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case PYGI_TYPE_UTF8:
      *out = GI_TYPE_TAG_UTF8;
      return true;
    case PYGI_TYPE_FILENAME:
      *out = GI_TYPE_TAG_FILENAME;
      return true;
    case PYGI_TYPE_ENUM:
      *out = GI_TYPE_TAG_INT32;
      return true;
    case PYGI_TYPE_FLAGS:
      *out = GI_TYPE_TAG_UINT32;
      return true;
    default:
      return false;
    }
}

bool
pygi_type_is_direct_storage (const PyGIType *type)
{
  GITypeTag tag = GI_TYPE_TAG_VOID;
  return pygi_type_storage_tag (type, &tag);
}

/**
 * pygi_type_storage_size:
 * @type: resolved GI type metadata
 *
 * Returns the raw byte size used by memory-target marshalling for
 * direct-storage types. Returns 0 when @type is unsupported, is not
 * stored inline by PyGIValue, or carries no C storage.
 */
gsize
pygi_type_storage_size (const PyGIType *type)
{
  GITypeTag tag = GI_TYPE_TAG_VOID;
  if (!pygi_type_storage_tag (type, &tag))
    return 0;

  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      return type->kind == PYGI_TYPE_POINTER ? sizeof (gpointer) : 0;
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      return sizeof (gchar *);
#define PYGI_SCALAR PYGI_SCALAR_RETURN_SIZE

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    default:
      return 0;
    }
}

static int
pygi_giarg_from_py (PyObject *py, const PyGIType *type, GIArgument *out)
{
  switch (type->kind)
    {
    case PYGI_TYPE_VOID:
      return pygi_void_from_py (py, out);
    case PYGI_TYPE_POINTER:
      if (py == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      if (PyLong_Check (py))
        {
          out->v_pointer = PyLong_AsVoidPtr (py);
          return PyErr_Occurred () ? -1 : 0;
        }
      out->v_pointer = NULL;
      return 0;
    case PYGI_TYPE_BOOLEAN:
      return pygi_boolean_from_py (py, out);
    case PYGI_TYPE_INT8:
      return pygi_int8_from_py (py, out);
    case PYGI_TYPE_UINT8:
      return pygi_uint8_from_py (py, out);
    case PYGI_TYPE_INT16:
      return pygi_int16_from_py (py, out);
    case PYGI_TYPE_UINT16:
      return pygi_uint16_from_py (py, out);
    case PYGI_TYPE_INT32:
      return pygi_int32_from_py (py, out);
    case PYGI_TYPE_UINT32:
      return pygi_uint32_from_py (py, out);
    case PYGI_TYPE_INT64:
      return pygi_int64_from_py (py, out);
    case PYGI_TYPE_UINT64:
      return pygi_uint64_from_py (py, out);
    case PYGI_TYPE_FLOAT:
      return pygi_float_from_py (py, out);
    case PYGI_TYPE_DOUBLE:
      return pygi_double_from_py (py, out);
    case PYGI_TYPE_UNICHAR:
      return pygi_unichar_from_py (py, out);
    case PYGI_TYPE_UTF8:
      return pygi_utf8_from_py (py, out);
    case PYGI_TYPE_FILENAME:
      return pygi_filename_from_py (py, out);
    case PYGI_TYPE_GTYPE:
      return pygi_gtype_from_py (py, out);
    case PYGI_TYPE_ENUM:
      return pygi_int32_from_py (py, out);
    case PYGI_TYPE_FLAGS:
      return pygi_uint32_from_py (py, out);
    default:
      PyErr_SetString (PyExc_NotImplementedError,
                       "pygi_value_from_py: unsupported GIArgument type");
      return -1;
    }
}

static PyObject *
pygi_giarg_to_py (const PyGIType *type, GIArgument *arg)
{
  switch (type->kind)
    {
    case PYGI_TYPE_VOID:
      Py_RETURN_NONE;
    case PYGI_TYPE_POINTER:
      if (arg->v_pointer == NULL)
        Py_RETURN_NONE;
      return PyLong_FromVoidPtr (arg->v_pointer);
#define PYGI_SCALAR PYGI_SCALAR_RETURN_PY_OBJECT

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case PYGI_TYPE_UTF8:
      return pygi_utf8_to_py (arg, type->transfer);
    case PYGI_TYPE_FILENAME:
      return pygi_filename_to_py (arg, type->transfer);
    case PYGI_TYPE_ENUM:
      return PyLong_FromLong ((long)arg->v_int32);
    case PYGI_TYPE_FLAGS:
      return PyLong_FromUnsignedLong ((unsigned long)arg->v_uint32);
    default:
      PyErr_SetString (PyExc_NotImplementedError, "pygi_value_to_py: unsupported GIArgument type");
      return NULL;
    }
}

static int
pygi_memory_load_giarg (const PyGIType *type, GITypeTag tag, const void *memory, GIArgument *out)
{
  void *dst = gi_argument_storage_pointer (tag, out);
  gsize size = pygi_type_storage_size (type);
  if (dst == NULL || size == 0)
    {
      PyErr_Format (PyExc_NotImplementedError,
                    "pygi_value_to_py: unsupported memory tag %s",
                    gi_type_tag_to_string (tag));
      return -1;
    }

  memcpy (dst, memory, size);
  return 0;
}

static int
pygi_memory_store_giarg (const PyGIType *type, GITypeTag tag, GIArgument *arg, void *memory)
{
  void *src = gi_argument_storage_pointer (tag, arg);
  gsize size = pygi_type_storage_size (type);
  if (src == NULL || size == 0)
    {
      PyErr_Format (PyExc_NotImplementedError,
                    "pygi_value_from_py: unsupported memory tag %s",
                    gi_type_tag_to_string (tag));
      return -1;
    }

  memcpy (memory, src, size);
  return 0;
}

static int
pygi_memory_from_py (PyObject *py, const PyGIType *type, void *memory)
{
  g_return_val_if_fail (memory != NULL, -1);
  GITypeTag tag = GI_TYPE_TAG_VOID;
  if (!pygi_type_storage_tag (type, &tag))
    {
      PyErr_SetString (PyExc_NotImplementedError, "pygi_value_from_py: unsupported memory type");
      return -1;
    }
  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      {
        if (py != Py_None)
          {
            PyErr_SetString (PyExc_TypeError, "expected None for opaque (void *) field");
            return -1;
          }
        *(gpointer *)memory = NULL;
        return 0;
      }
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      {
        gchar **slot = (gchar **)memory;
        g_free (*slot);
        if (py == Py_None)
          {
            *slot = NULL;
            return 0;
          }
        if (!PyUnicode_Check (py))
          {
            PyErr_SetString (PyExc_TypeError, "expected str (or None) for utf8 field");
            *slot = NULL;
            return -1;
          }
        const char *s = PyUnicode_AsUTF8 (py);
        if (s == NULL)
          {
            *slot = NULL;
            return -1;
          }
        *slot = g_strdup (s);
        return 0;
      }
    default:
      {
        GIArgument arg = { 0 };
        if (pygi_giarg_from_py (py, type, &arg) != 0)
          return -1;
        return pygi_memory_store_giarg (type, tag, &arg, memory);
      }
    }
}

static PyObject *
pygi_memory_to_py (const PyGIType *type, const void *memory)
{
  g_return_val_if_fail (memory != NULL, NULL);
  GITypeTag tag = GI_TYPE_TAG_VOID;
  if (!pygi_type_storage_tag (type, &tag))
    {
      PyErr_SetString (PyExc_NotImplementedError, "pygi_value_to_py: unsupported memory type");
      return NULL;
    }
  switch (tag)
    {
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      {
        const char *s = *(const char *const *)memory;
        if (s == NULL)
          Py_RETURN_NONE;
        return PyUnicode_FromString (s);
      }
    case GI_TYPE_TAG_VOID:
      {
        gpointer ptr = *(gpointer const *)memory;
        if (ptr == NULL)
          Py_RETURN_NONE;
        return PyLong_FromVoidPtr (ptr);
      }
    default:
      {
        GIArgument arg = { 0 };
        if (pygi_memory_load_giarg (type, tag, memory, &arg) != 0)
          return NULL;
        return pygi_giarg_to_py (type, &arg);
      }
    }
}

static int
pygi_value_gvalue_from_py (PyObject *py, const PyGIType *type, GValue *value)
{
  if (type->gtype == G_TYPE_INVALID || type->gtype == 0)
    {
      PyErr_SetString (PyExc_SystemError, "pygi_value_from_py: GValue target missing GType");
      return -1;
    }
  if (G_VALUE_TYPE (value) == 0)
    g_value_init (value, type->gtype);

  if (type->gtype == G_TYPE_GTYPE)
    {
      GType v = G_TYPE_INVALID;
      if (pygi_gtype_from_py_object (py, &v) != 0)
        return -1;
      g_value_set_gtype (value, v);
      return 0;
    }

  switch (G_TYPE_FUNDAMENTAL (type->gtype))
    {
    case G_TYPE_STRING:
      if (py == Py_None)
        {
          g_value_set_string (value, NULL);
          return 0;
        }
      {
        const char *s = PyUnicode_AsUTF8 (py);
        if (s == NULL)
          return -1;
        g_value_set_string (value, s);
        return 0;
      }
    case G_TYPE_BOOLEAN:
      {
        int truth = PyObject_IsTrue (py);
        if (truth < 0)
          return -1;
        g_value_set_boolean (value, truth != 0);
        return 0;
      }
    case G_TYPE_CHAR:
      {
        long v = pygi_pyobj_to_long (py);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        g_value_set_schar (value, (gint8)v);
        return 0;
      }
    case G_TYPE_UCHAR:
      {
        unsigned long v = pygi_pyobj_to_ulong_mask (py);
        if (v == (unsigned long)-1 && PyErr_Occurred ())
          return -1;
        g_value_set_uchar (value, (guchar)v);
        return 0;
      }
    case G_TYPE_INT:
      {
        long v = pygi_pyobj_to_long (py);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        g_value_set_int (value, (gint)v);
        return 0;
      }
    case G_TYPE_UINT:
      {
        unsigned long v = pygi_pyobj_to_ulong_mask (py);
        if (v == (unsigned long)-1 && PyErr_Occurred ())
          return -1;
        g_value_set_uint (value, (guint)v);
        return 0;
      }
    case G_TYPE_LONG:
      {
        long v = pygi_pyobj_to_long (py);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        g_value_set_long (value, v);
        return 0;
      }
    case G_TYPE_ULONG:
      {
        unsigned long v = pygi_pyobj_to_ulong_mask (py);
        if (v == (unsigned long)-1 && PyErr_Occurred ())
          return -1;
        g_value_set_ulong (value, v);
        return 0;
      }
    case G_TYPE_INT64:
      {
        long long v = pygi_pyobj_to_longlong (py);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        g_value_set_int64 (value, (gint64)v);
        return 0;
      }
    case G_TYPE_UINT64:
      {
        unsigned long long v = pygi_pyobj_to_ulonglong (py);
        if (v == (unsigned long long)-1 && PyErr_Occurred ())
          return -1;
        g_value_set_uint64 (value, (guint64)v);
        return 0;
      }
    case G_TYPE_FLOAT:
      {
        double v = PyFloat_AsDouble (py);
        if (v == -1.0 && PyErr_Occurred ())
          return -1;
        g_value_set_float (value, (gfloat)v);
        return 0;
      }
    case G_TYPE_DOUBLE:
      {
        double v = PyFloat_AsDouble (py);
        if (v == -1.0 && PyErr_Occurred ())
          return -1;
        g_value_set_double (value, v);
        return 0;
      }
    case G_TYPE_POINTER:
      if (g_strcmp0 (g_type_name (type->gtype), "PyObject") == 0)
        {
          g_value_set_pointer (value, py == Py_None ? NULL : py);
          return 0;
        }
      if (py == Py_None)
        {
          g_value_set_pointer (value, NULL);
          return 0;
        }
      if (!PyLong_Check (py))
        {
          PyErr_SetString (PyExc_TypeError, "gpointer GValue expects None or an integer pointer");
          return -1;
        }
      g_value_set_pointer (value, PyLong_AsVoidPtr (py));
      if (PyErr_Occurred ())
        return -1;
      return 0;
    default:
      break;
    }

  PyErr_SetString (PyExc_NotImplementedError, "pygi_value_from_py: unsupported GValue type");
  return -1;
}

static PyObject *
pygi_value_gvalue_to_py (GValue *value)
{
  GType gtype = G_VALUE_TYPE (value);
  if (gtype == 0)
    Py_RETURN_NONE;

  if (gtype == G_TYPE_BOOLEAN)
    return PyBool_FromLong (g_value_get_boolean (value));
  if (gtype == G_TYPE_CHAR)
    return PyLong_FromLong (g_value_get_schar (value));
  if (gtype == G_TYPE_UCHAR)
    return PyLong_FromLong (g_value_get_uchar (value));
  if (gtype == G_TYPE_INT)
    return PyLong_FromLong (g_value_get_int (value));
  if (gtype == G_TYPE_UINT)
    return PyLong_FromUnsignedLong (g_value_get_uint (value));
  if (gtype == G_TYPE_LONG)
    return PyLong_FromLongLong (g_value_get_long (value));
  if (gtype == G_TYPE_ULONG)
    return PyLong_FromUnsignedLongLong (g_value_get_ulong (value));
  if (gtype == G_TYPE_INT64)
    return PyLong_FromLongLong (g_value_get_int64 (value));
  if (gtype == G_TYPE_UINT64)
    return PyLong_FromUnsignedLongLong (g_value_get_uint64 (value));
  if (gtype == G_TYPE_FLOAT)
    return PyFloat_FromDouble (g_value_get_float (value));
  if (gtype == G_TYPE_DOUBLE)
    return PyFloat_FromDouble (g_value_get_double (value));
  if (gtype == G_TYPE_GTYPE)
    return pygi_gtype_value_to_py (g_value_get_gtype (value));
  if (gtype == G_TYPE_STRING)
    {
      const char *s = g_value_get_string (value);
      return s ? PyUnicode_FromString (s) : Py_XNewRef (Py_None);
    }
  if (G_TYPE_FUNDAMENTAL (gtype) == G_TYPE_POINTER)
    {
      gpointer ptr = g_value_get_pointer (value);
      if (ptr == NULL)
        Py_RETURN_NONE;
      if (g_strcmp0 (g_type_name (gtype), "PyObject") == 0)
        return Py_NewRef ((PyObject *)ptr);
      return PyLong_FromVoidPtr (ptr);
    }

  PyErr_SetString (PyExc_NotImplementedError, "pygi_value_to_py: unsupported GValue type");
  return NULL;
}

int
pygi_value_from_py (PyObject *py, PyGIValue *out)
{
  g_return_val_if_fail (out != NULL, -1);
  g_return_val_if_fail (out->type != NULL, -1);

  switch (out->storage)
    {
    case PYGI_VALUE_STORAGE_GIARG:
      g_return_val_if_fail (out->as.giarg != NULL, -1);
      return pygi_giarg_from_py (py, out->type, out->as.giarg);
    case PYGI_VALUE_STORAGE_GVALUE:
      g_return_val_if_fail (out->as.gvalue != NULL, -1);
      return pygi_value_gvalue_from_py (py, out->type, out->as.gvalue);
    case PYGI_VALUE_STORAGE_MEMORY:
      g_return_val_if_fail (out->as.memory != NULL, -1);
      return pygi_memory_from_py (py, out->type, out->as.memory);
    }
  PyErr_SetString (PyExc_SystemError, "pygi_value_from_py: unknown storage kind");
  return -1;
}

PyObject *
pygi_value_to_py (const PyGIValue *value)
{
  g_return_val_if_fail (value != NULL, NULL);
  g_return_val_if_fail (value->type != NULL, NULL);

  switch (value->storage)
    {
    case PYGI_VALUE_STORAGE_GIARG:
      g_return_val_if_fail (value->as.giarg != NULL, NULL);
      return pygi_giarg_to_py (value->type, value->as.giarg);
    case PYGI_VALUE_STORAGE_GVALUE:
      g_return_val_if_fail (value->as.gvalue != NULL, NULL);
      return pygi_value_gvalue_to_py (value->as.gvalue);
    case PYGI_VALUE_STORAGE_MEMORY:
      g_return_val_if_fail (value->as.memory != NULL, NULL);
      return pygi_memory_to_py (value->type, value->as.memory);
    }
  PyErr_SetString (PyExc_SystemError, "pygi_value_to_py: unknown storage kind");
  return NULL;
}
