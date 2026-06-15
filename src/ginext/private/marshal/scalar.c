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

/* scalar.c - scalar GI type marshaling:
 * VOID, BOOLEAN, INT8/16/32/64, UINT8/16/32/64, FLOAT, DOUBLE, UNICHAR,
 * GTYPE, plus shared primitive C storage helpers. */

#include "marshal/scalar.h"
#include "marshal/pygi-value.h"
#include "marshal/marshal.h"
#include "runtime/type-info.h"
#include "gimeta-helpers.h"

#include <glib.h>
#include <math.h>
#include <stdint.h>

/* --------------------------------------------------------------------- */
/* Helpers                                                                */
/* --------------------------------------------------------------------- */

/* Range-check a PyLong against [min_v, max_v]. On out-of-range, raises
 * OverflowError formatted as "<value> not in range <min> to <max>" to
 * match PyGObject's user-visible message (the actual value is critical
 * for diagnostics — generic "value outside int8 range" hides what the
 * caller actually passed). Returns 0 in range, -1 out of range. */
static int
pygi_long_check_signed_bounds (PyObject *long_obj, long long min_v, long long max_v)
{
  PyObject *min_py = PyLong_FromLongLong (min_v);
  if (min_py == NULL)
    return -1;
  PyObject *max_py = PyLong_FromLongLong (max_v);
  if (max_py == NULL)
    {
      Py_DECREF (min_py);
      return -1;
    }
  int below = PyObject_RichCompareBool (long_obj, min_py, Py_LT);
  int above = below == 0 ? PyObject_RichCompareBool (long_obj, max_py, Py_GT) : 0;
  Py_DECREF (min_py);
  Py_DECREF (max_py);
  if (below < 0 || above < 0)
    return -1;
  if (below || above)
    {
      PyObject *str = PyObject_Str (long_obj);
      if (str != NULL)
        {
          PyErr_Format (PyExc_OverflowError, "%U not in range %lld to %lld", str, min_v, max_v);
          Py_DECREF (str);
        }
      return -1;
    }
  return 0;
}

static int
pygi_long_check_unsigned_bounds (PyObject *long_obj, unsigned long long max_v)
{
  PyObject *zero = PyLong_FromLong (0);
  if (zero == NULL)
    return -1;
  PyObject *max_py = PyLong_FromUnsignedLongLong (max_v);
  if (max_py == NULL)
    {
      Py_DECREF (zero);
      return -1;
    }
  int below = PyObject_RichCompareBool (long_obj, zero, Py_LT);
  int above = below == 0 ? PyObject_RichCompareBool (long_obj, max_py, Py_GT) : 0;
  Py_DECREF (zero);
  Py_DECREF (max_py);
  if (below < 0 || above < 0)
    return -1;
  if (below || above)
    {
      PyObject *str = PyObject_Str (long_obj);
      if (str != NULL)
        {
          PyErr_Format (PyExc_OverflowError, "%U not in range 0 to %llu", str, max_v);
          Py_DECREF (str);
        }
      return -1;
    }
  return 0;
}

static int
pygi_float_check_bounds (PyObject *obj, double value, double min_v, double max_v)
{
  if (!isfinite (value) || value < min_v || value > max_v)
    {
      PyObject *str = PyObject_Str (obj);
      PyObject *min_py = PyFloat_FromDouble (min_v);
      PyObject *max_py = PyFloat_FromDouble (max_v);
      if (str != NULL && min_py != NULL && max_py != NULL)
        {
          PyErr_Format (PyExc_OverflowError, "%U not in range %S to %S", str, min_py, max_py);
        }
      Py_XDECREF (str);
      Py_XDECREF (min_py);
      Py_XDECREF (max_py);
      return -1;
    }
  return 0;
}

/* --------------------------------------------------------------------- */
/* VOID                                                                   */
/* --------------------------------------------------------------------- */

int
pygi_void_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  (void)h;
  out->v_pointer = NULL;
  return 0;
}

/* --------------------------------------------------------------------- */
/* BOOLEAN                                                                */
/* --------------------------------------------------------------------- */

int
pygi_boolean_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  int truth = PyObject_IsTrue (h);
  if (truth < 0)
    return -1;
  out->v_boolean = truth != 0;
  return 0;
}

/* --------------------------------------------------------------------- */
/* INT8 / UINT8 / INT16 / UINT16 / INT32 / UINT32                         */
/* --------------------------------------------------------------------- */

static PyObject *
pygi_pyobj_to_8bit_long_object (PyObject *h)
{
  if (PyUnicode_Check (h))
    {
      if (PyUnicode_GetLength (h) != 1)
        {
          PyErr_Format (PyExc_TypeError,
                        "'%.80s' object cannot be interpreted as an integer",
                        Py_TYPE (h)->tp_name);
          return NULL;
        }
      Py_UCS4 ch = PyUnicode_ReadChar (h, 0);
      if (ch == (Py_UCS4)-1 && PyErr_Occurred ())
        return NULL;
      return PyLong_FromUnsignedLong ((unsigned long)ch);
    }

  if (PyBytes_Check (h))
    {
      if (PyBytes_GET_SIZE (h) != 1)
        {
          PyErr_Format (PyExc_TypeError,
                        "'%.80s' object cannot be interpreted as an integer",
                        Py_TYPE (h)->tp_name);
          return NULL;
        }
      return PyLong_FromUnsignedLong ((unsigned char)PyBytes_AS_STRING (h)[0]);
    }

  if (PyByteArray_Check (h))
    {
      if (PyByteArray_GET_SIZE (h) != 1)
        {
          PyErr_Format (PyExc_TypeError,
                        "'%.80s' object cannot be interpreted as an integer",
                        Py_TYPE (h)->tp_name);
          return NULL;
        }
      return PyLong_FromUnsignedLong ((unsigned char)PyByteArray_AS_STRING (h)[0]);
    }

  return pygi_pyobj_to_long_object (h);
}

int
pygi_int8_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  PyObject *long_obj = pygi_pyobj_to_8bit_long_object (h);
  if (long_obj == NULL)
    return -1;
  if (pygi_long_check_signed_bounds (long_obj, INT8_MIN, INT8_MAX) != 0)
    {
      Py_DECREF (long_obj);
      return -1;
    }
  long value = PyLong_AsLong (long_obj);
  Py_DECREF (long_obj);
  if (value == -1 && PyErr_Occurred ())
    return -1;
  out->v_int8 = (int8_t)value;
  return 0;
}

int
pygi_uint8_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  PyObject *long_obj = pygi_pyobj_to_8bit_long_object (h);
  if (long_obj == NULL)
    return -1;
  if (pygi_long_check_unsigned_bounds (long_obj, UINT8_MAX) != 0)
    {
      Py_DECREF (long_obj);
      return -1;
    }
  unsigned long value = PyLong_AsUnsignedLong (long_obj);
  Py_DECREF (long_obj);
  if (value == (unsigned long)-1 && PyErr_Occurred ())
    return -1;
  out->v_uint8 = (uint8_t)value;
  return 0;
}

int
pygi_int16_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  PyObject *long_obj = pygi_pyobj_to_long_object (h);
  if (long_obj == NULL)
    return -1;
  if (pygi_long_check_signed_bounds (long_obj, INT16_MIN, INT16_MAX) != 0)
    {
      Py_DECREF (long_obj);
      return -1;
    }
  long value = PyLong_AsLong (long_obj);
  Py_DECREF (long_obj);
  if (value == -1 && PyErr_Occurred ())
    return -1;
  out->v_int16 = (int16_t)value;
  return 0;
}

int
pygi_uint16_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  PyObject *long_obj = pygi_pyobj_to_long_object (h);
  if (long_obj == NULL)
    return -1;
  if (pygi_long_check_unsigned_bounds (long_obj, UINT16_MAX) != 0)
    {
      Py_DECREF (long_obj);
      return -1;
    }
  unsigned long value = PyLong_AsUnsignedLong (long_obj);
  Py_DECREF (long_obj);
  if (value == (unsigned long)-1 && PyErr_Occurred ())
    return -1;
  out->v_uint16 = (uint16_t)value;
  return 0;
}

int
pygi_int32_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  PyObject *long_obj = pygi_pyobj_to_long_object (h);
  if (long_obj == NULL)
    return -1;
  if (pygi_long_check_signed_bounds (long_obj, INT32_MIN, INT32_MAX) != 0)
    {
      Py_DECREF (long_obj);
      return -1;
    }
  long value = PyLong_AsLong (long_obj);
  Py_DECREF (long_obj);
  if (value == -1 && PyErr_Occurred ())
    return -1;
  out->v_int32 = (int32_t)value;
  return 0;
}

int
pygi_uint32_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  PyObject *long_obj = pygi_pyobj_to_long_object (h);
  if (long_obj == NULL)
    return -1;
  if (pygi_long_check_unsigned_bounds (long_obj, UINT32_MAX) != 0)
    {
      Py_DECREF (long_obj);
      return -1;
    }
  unsigned long value = PyLong_AsUnsignedLong (long_obj);
  Py_DECREF (long_obj);
  if (value == (unsigned long)-1 && PyErr_Occurred ())
    return -1;
  out->v_uint32 = (uint32_t)value;
  return 0;
}

/* --------------------------------------------------------------------- */
/* INT64 / UINT64                                                         */
/* --------------------------------------------------------------------- */

int
pygi_int64_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  PyObject *long_obj = pygi_pyobj_to_long_object (h);
  if (long_obj == NULL)
    return -1;
  if (pygi_long_check_signed_bounds (long_obj, INT64_MIN, INT64_MAX) != 0)
    {
      Py_DECREF (long_obj);
      return -1;
    }
  long long value = PyLong_AsLongLong (long_obj);
  Py_DECREF (long_obj);
  if (value == -1 && PyErr_Occurred ())
    return -1;
  out->v_int64 = (int64_t)value;
  return 0;
}

int
pygi_uint64_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  PyObject *long_obj = pygi_pyobj_to_long_object (h);
  if (long_obj == NULL)
    return -1;
  if (pygi_long_check_unsigned_bounds (long_obj, UINT64_MAX) != 0)
    {
      Py_DECREF (long_obj);
      return -1;
    }
  unsigned long long value = PyLong_AsUnsignedLongLong (long_obj);
  Py_DECREF (long_obj);
  if (value == (unsigned long long)-1 && PyErr_Occurred ())
    return -1;
  out->v_uint64 = (uint64_t)value;
  return 0;
}

/* --------------------------------------------------------------------- */
/* FLOAT / DOUBLE                                                         */
/* --------------------------------------------------------------------- */

int
pygi_float_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  double value = PyFloat_AsDouble (h);
  if (value == -1.0 && PyErr_Occurred ())
    return -1;
  if (pygi_float_check_bounds (h, value, -G_MAXFLOAT, G_MAXFLOAT) != 0)
    return -1;
  out->v_float = (float)value;
  return 0;
}

int
pygi_double_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  double value = PyFloat_AsDouble (h);
  if (value == -1.0 && PyErr_Occurred ())
    return -1;
  if (pygi_float_check_bounds (h, value, -G_MAXDOUBLE, G_MAXDOUBLE) != 0)
    return -1;
  out->v_double = value;
  return 0;
}

/* --------------------------------------------------------------------- */
/* UNICHAR                                                                */
/* --------------------------------------------------------------------- */

int
pygi_unichar_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  if (PyUnicode_Check (h))
    {
      if (PyUnicode_GetLength (h) != 1)
        {
          PyErr_SetString (PyExc_ValueError, "unichar requires a 1-char string");
          return -1;
        }
      out->v_uint32 = (uint32_t)PyUnicode_ReadChar (h, 0);
      return PyErr_Occurred () ? -1 : 0;
    }
  out->v_uint32 = (uint32_t)PyLong_AsUnsignedLong (h);
  return PyErr_Occurred () ? -1 : 0;
}

/* --------------------------------------------------------------------- */
/* GTYPE                                                                  */
/* --------------------------------------------------------------------- */

int
pygi_gtype_from_py (PyObject *h, GIArgument *out)
{
  g_return_val_if_fail (out != NULL, -1);
  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (h, &gtype) != 0)
    return -1;
  out->v_size = (size_t)gtype;
  return 0;
}

/* --------------------------------------------------------------------- */
/* Shared primitive C storage helpers                                     */
/* --------------------------------------------------------------------- */

int
pygi_py_to_primitive_storage (PyObject *item, GITypeTag tag, void *dst)
{
  g_return_val_if_fail (dst != NULL, -1);
  PyGIType type = { 0 };
  if (pygi_type_from_gi_tag (tag, tag == GI_TYPE_TAG_VOID, &type) != 0)
    {
      PyErr_Format (PyExc_NotImplementedError,
                    "primitive marshal: unsupported tag %s",
                    gi_type_tag_to_string (tag));
      return -1;
    }
  PyGIValue value = pygi_value_for_memory (&type, dst);
  return pygi_value_from_py (item, &value);
}

PyObject *
pygi_primitive_storage_to_py (GITypeTag tag, const void *src)
{
  g_return_val_if_fail (src != NULL, NULL);
  PyGIType type = { 0 };
  if (pygi_type_from_gi_tag (tag, tag == GI_TYPE_TAG_VOID, &type) != 0)
    {
      PyErr_Format (PyExc_NotImplementedError,
                    "primitive marshal: unsupported tag %s",
                    gi_type_tag_to_string (tag));
      return NULL;
    }
  PyGIValue value = pygi_value_for_memory (&type, (void *)src);
  return pygi_value_to_py (&value);
}

int
pygi_struct_info_copy_py_attrs_to_buffer (PyObject *src, GIBaseInfo *iface, char *buf)
{
  g_return_val_if_fail (src != NULL, -1);
  g_return_val_if_fail (iface != NULL, -1);
  g_return_val_if_fail (GI_IS_BASE_INFO (iface), -1);
  g_return_val_if_fail (buf != NULL, -1);
  int n_fields = gi_struct_or_union_n_fields (iface);
  for (int fi = 0; fi < n_fields; fi++)
    {
      g_autoptr (GIFieldInfo) field = gi_struct_or_union_get_field (iface, (guint)fi);
      if (field == NULL)
        continue;
      if (!(gi_field_info_get_flags (field) & GI_FIELD_IS_WRITABLE))
        continue;
      const char *fname = gi_base_info_get_name ((GIBaseInfo *)field);
      PyObject *attr = PyObject_GetAttrString (src, fname);
      if (attr == NULL)
        {
          PyErr_Clear ();
          continue;
        }
      g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
      char *dst = buf + gi_field_info_get_offset (field);
      PyGIType field_type = { 0 };
      if (pygi_type_from_gi (fti, &field_type) != 0 || !pygi_type_is_direct_storage (&field_type))
        {
          Py_DECREF (attr);
          continue;
        }
      if (pygi_marshal_from_py (attr,
                                &(PyGIMarshalSlot){
                                    .type = fti,
                                    .pygi_type = &field_type,
                                    .transfer = GI_TRANSFER_NOTHING,
                                    .transfer_set = true,
                                    .kind = PYGI_MARSHAL_TARGET_MEMORY,
                                    .target.memory = dst,
                                })
          != 0)
        {
          Py_DECREF (attr);
          return -1;
        }
      Py_DECREF (attr);
    }
  return 0;
}
