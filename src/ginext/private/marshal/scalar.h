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

#pragma once

/* Scalar GI type marshaling: Python <-> GIArgument for all primitive
 * GI_TYPE_TAG values (VOID, BOOLEAN, INT8/16/32/64, UINT8/16/32/64,
 * FLOAT, DOUBLE, UNICHAR, GTYPE) plus shared primitive C storage helpers.
 * For UTF8 and FILENAME see string.h. */

#include <Python.h>
#include <stdint.h>
#include <girepository/girepository.h>

#define PYGI_SCALAR_RETURN_TRUE(NAME,                                                              \
                                TAG,                                                               \
                                CTYPE,                                                             \
                                FIELD,                                                             \
                                MIN,                                                               \
                                MAX,                                                               \
                                PY_CTOR,                                                           \
                                PY_CAST,                                                           \
                                LENGTH_SUPPORTED)                                                  \
  case TAG:                                                                                        \
    return TRUE;

#define PYGI_SCALAR_RETURN_PYGI_TYPE_KIND(NAME,                                                    \
                                          TAG,                                                     \
                                          CTYPE,                                                   \
                                          FIELD,                                                   \
                                          MIN,                                                     \
                                          MAX,                                                     \
                                          PY_CTOR,                                                 \
                                          PY_CAST,                                                 \
                                          LENGTH_SUPPORTED)                                        \
  case TAG:                                                                                        \
    return PYGI_TYPE_##NAME;

#define PYGI_SCALAR_SET_GI_TYPE_TAG(NAME,                                                          \
                                    TAG,                                                           \
                                    CTYPE,                                                         \
                                    FIELD,                                                         \
                                    MIN,                                                           \
                                    MAX,                                                           \
                                    PY_CTOR,                                                       \
                                    PY_CAST,                                                       \
                                    LENGTH_SUPPORTED)                                              \
  case PYGI_TYPE_##NAME:                                                                           \
    *out = TAG;                                                                                    \
    return true;

#define PYGI_SCALAR_RETURN_SIZE(NAME,                                                              \
                                TAG,                                                               \
                                CTYPE,                                                             \
                                FIELD,                                                             \
                                MIN,                                                               \
                                MAX,                                                               \
                                PY_CTOR,                                                           \
                                PY_CAST,                                                           \
                                LENGTH_SUPPORTED)                                                  \
  case TAG:                                                                                        \
    return sizeof (CTYPE);

#define PYGI_SCALAR_GET_LENGTH(NAME,                                                               \
                               TAG,                                                                \
                               CTYPE,                                                              \
                               FIELD,                                                              \
                               MIN,                                                                \
                               MAX,                                                                \
                               PY_CTOR,                                                            \
                               PY_CAST,                                                            \
                               LENGTH_SUPPORTED)                                                   \
  case TAG:                                                                                        \
    if (!LENGTH_SUPPORTED)                                                                         \
      return -1;                                                                                   \
    if ((MIN) < 0 && (gint64)arg->FIELD < 0)                                                       \
      return -1;                                                                                   \
    *out = (gsize)arg->FIELD;                                                                      \
    return 0;

#define PYGI_SCALAR_SET_LENGTH(NAME,                                                               \
                               TAG,                                                                \
                               CTYPE,                                                              \
                               FIELD,                                                              \
                               MIN,                                                                \
                               MAX,                                                                \
                               PY_CTOR,                                                            \
                               PY_CAST,                                                            \
                               LENGTH_SUPPORTED)                                                   \
  case TAG:                                                                                        \
    if (!LENGTH_SUPPORTED)                                                                         \
      return -1;                                                                                   \
    out->FIELD = (CTYPE)len;                                                                       \
    return 0;

#define PYGI_SCALAR_RETURN_PY_OBJECT(NAME,                                                         \
                                     TAG,                                                          \
                                     CTYPE,                                                        \
                                     FIELD,                                                        \
                                     MIN,                                                          \
                                     MAX,                                                          \
                                     PY_CTOR,                                                      \
                                     PY_CAST,                                                      \
                                     LENGTH_SUPPORTED)                                             \
  case PYGI_TYPE_##NAME:                                                                           \
    return PY_CTOR ((PY_CAST)arg->FIELD);

#define PYGI_SCALAR_SET_RESULT_FROM_VALUE(NAME,                                                    \
                                          TAG,                                                     \
                                          CTYPE,                                                   \
                                          FIELD,                                                   \
                                          MIN,                                                     \
                                          MAX,                                                     \
                                          PY_CTOR,                                                 \
                                          PY_CAST,                                                 \
                                          LENGTH_SUPPORTED)                                        \
  case TAG:                                                                                        \
    result = PY_CTOR ((PY_CAST)value.FIELD);                                                       \
    break;

#define PYGI_SCALAR_RETURN_GIARG_FIELD_POINTER(NAME,                                               \
                                               TAG,                                                \
                                               CTYPE,                                              \
                                               FIELD,                                              \
                                               MIN,                                                \
                                               MAX,                                                \
                                               PY_CTOR,                                            \
                                               PY_CAST,                                            \
                                               LENGTH_SUPPORTED)                                   \
  case TAG:                                                                                        \
    return &arg->FIELD;

#define PYGI_SCALAR_LOAD_ALIGNED_FROM_SRC(NAME,                                                    \
                                          TAG,                                                     \
                                          CTYPE,                                                   \
                                          FIELD,                                                   \
                                          MIN,                                                     \
                                          MAX,                                                     \
                                          PY_CTOR,                                                 \
                                          PY_CAST,                                                 \
                                          LENGTH_SUPPORTED)                                        \
  case TAG:                                                                                        \
    aligned.FIELD = *(CTYPE *)src;                                                                 \
    break;

#define PYGI_SCALAR_LOAD_OUT_FROM_PTR(NAME,                                                        \
                                      TAG,                                                         \
                                      CTYPE,                                                       \
                                      FIELD,                                                       \
                                      MIN,                                                         \
                                      MAX,                                                         \
                                      PY_CTOR,                                                     \
                                      PY_CAST,                                                     \
                                      LENGTH_SUPPORTED)                                            \
  case TAG:                                                                                        \
    out->FIELD = *(const CTYPE *)ptr;                                                              \
    return 0;

/* Float/object->int coercion helpers (matches PyGObject's
 * PyNumber_Long-based path: passing a float to a GIR int parameter
 * truncates to long, and objects with __int__ are accepted). Plain
 * PyLong inputs go straight through PyLong_As*. */
static inline PyObject *
pygi_pyobj_to_long_object (PyObject *o)
{
  if (PyLong_Check (o))
    {
      Py_INCREF (o);
      return o;
    }

  if (PyUnicode_Check (o) || PyBytes_Check (o) || PyByteArray_Check (o))
    {
      PyErr_Format (PyExc_TypeError,
                    "'%.80s' object cannot be interpreted as an integer",
                    Py_TYPE (o)->tp_name);
      return NULL;
    }

  PyObject *long_obj = PyNumber_Long (o);
  if (long_obj == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_TypeError) || PyErr_ExceptionMatches (PyExc_ValueError))
        {
          PyErr_Clear ();
          PyErr_Format (PyExc_TypeError,
                        "'%.80s' object cannot be interpreted as an integer",
                        Py_TYPE (o)->tp_name);
        }
      return NULL;
    }

  return long_obj;
}

static inline long
pygi_pyobj_to_long (PyObject *o)
{
  PyObject *long_obj = pygi_pyobj_to_long_object (o);
  if (long_obj == NULL)
    return -1;
  long value = PyLong_AsLong (long_obj);
  Py_DECREF (long_obj);
  return value;
}

static inline long long
pygi_pyobj_to_longlong (PyObject *o)
{
  PyObject *long_obj = pygi_pyobj_to_long_object (o);
  if (long_obj == NULL)
    return -1;
  long long value = PyLong_AsLongLong (long_obj);
  Py_DECREF (long_obj);
  return value;
}

static inline unsigned long
pygi_pyobj_to_ulong_mask (PyObject *o)
{
  PyObject *long_obj = pygi_pyobj_to_long_object (o);
  if (long_obj == NULL)
    return (unsigned long)-1;
  unsigned long value = PyLong_AsUnsignedLongMask (long_obj);
  Py_DECREF (long_obj);
  return value;
}

static inline unsigned long long
pygi_pyobj_to_ulonglong (PyObject *o)
{
  PyObject *long_obj = pygi_pyobj_to_long_object (o);
  if (long_obj == NULL)
    return (unsigned long long)-1;
  unsigned long long value = PyLong_AsUnsignedLongLong (long_obj);
  Py_DECREF (long_obj);
  return value;
}

/* VOID */
int
pygi_void_from_py (PyObject *h, GIArgument *out);

/* BOOLEAN */
int
pygi_boolean_from_py (PyObject *h, GIArgument *out);

/* INT8 */
int
pygi_int8_from_py (PyObject *h, GIArgument *out);

/* UINT8 */
int
pygi_uint8_from_py (PyObject *h, GIArgument *out);

/* INT16 */
int
pygi_int16_from_py (PyObject *h, GIArgument *out);

/* UINT16 */
int
pygi_uint16_from_py (PyObject *h, GIArgument *out);

/* INT32 */
int
pygi_int32_from_py (PyObject *h, GIArgument *out);

/* UINT32 */
int
pygi_uint32_from_py (PyObject *h, GIArgument *out);

/* INT64 */
int
pygi_int64_from_py (PyObject *h, GIArgument *out);

/* UINT64 */
int
pygi_uint64_from_py (PyObject *h, GIArgument *out);

/* FLOAT */
int
pygi_float_from_py (PyObject *h, GIArgument *out);

/* DOUBLE */
int
pygi_double_from_py (PyObject *h, GIArgument *out);

/* UNICHAR */
int
pygi_unichar_from_py (PyObject *h, GIArgument *out);

/* GTYPE */
int
pygi_gtype_from_py (PyObject *h, GIArgument *out);

/* Shared primitive C storage helpers (from runtime/primitive.h) */

/* Read a Python integer/float/bool/1-char string from `item` and write the
 * corresponding C primitive into `*dst` according to `tag`. Returns 0 on
 * success; -1 with a Python exception set on failure. UNICHAR accepts either
 * a 1-char Python string or an integer code point. Unsupported tags raise
 * NotImplementedError. */
int
pygi_py_to_primitive_storage (PyObject *item, GITypeTag tag, void *dst);

/* Inverse of pygi_py_to_primitive_storage: read a primitive C value from
 * `*src` and return a new owning Python reference. Returns NULL on failure
 * with a Python exception set. */
PyObject *
pygi_primitive_storage_to_py (GITypeTag tag, const void *src);

/* Copy primitive attributes from `src` (a Python object with attributes named
 * after each field) into the C struct/union buffer `buf`. `iface` must be a
 * GIStructInfo or GIUnionInfo. Non-direct fields and missing attributes are
 * skipped. Returns -1 when a present direct field fails conversion. */
int
pygi_struct_info_copy_py_attrs_to_buffer (PyObject *src, GIBaseInfo *iface, char *buf);
