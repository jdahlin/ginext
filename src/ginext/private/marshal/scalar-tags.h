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

/* Scalar GI type metadata for X-macro generated switches.
 *
 * Include this file after defining:
 *
 *   PYGI_SCALAR(name, gi_tag, c_type, giarg_field, min_value, max_value,
 *               py_ctor, py_cast, length_supported)
 *
 * `py_ctor` and `py_cast` are the Python constructor and C cast used when
 * converting a GIArgument field to a Python object.
 */

PYGI_SCALAR (BOOLEAN, GI_TYPE_TAG_BOOLEAN, gboolean, v_boolean, 0, 1, PyBool_FromLong, long, 0)

PYGI_SCALAR (INT8, GI_TYPE_TAG_INT8, gint8, v_int8, INT8_MIN, INT8_MAX, PyLong_FromLong, long, 1)
PYGI_SCALAR (UINT8,
             GI_TYPE_TAG_UINT8,
             guint8,
             v_uint8,
             0,
             UINT8_MAX,
             PyLong_FromUnsignedLong,
             unsigned long,
             1)
PYGI_SCALAR (INT16,
             GI_TYPE_TAG_INT16,
             gint16,
             v_int16,
             INT16_MIN,
             INT16_MAX,
             PyLong_FromLong,
             long,
             1)
PYGI_SCALAR (UINT16,
             GI_TYPE_TAG_UINT16,
             guint16,
             v_uint16,
             0,
             UINT16_MAX,
             PyLong_FromUnsignedLong,
             unsigned long,
             1)
PYGI_SCALAR (INT32,
             GI_TYPE_TAG_INT32,
             gint32,
             v_int32,
             INT32_MIN,
             INT32_MAX,
             PyLong_FromLong,
             long,
             1)
PYGI_SCALAR (UINT32,
             GI_TYPE_TAG_UINT32,
             guint32,
             v_uint32,
             0,
             UINT32_MAX,
             PyLong_FromUnsignedLong,
             unsigned long,
             1)
PYGI_SCALAR (INT64,
             GI_TYPE_TAG_INT64,
             gint64,
             v_int64,
             INT64_MIN,
             INT64_MAX,
             PyLong_FromLongLong,
             long long,
             1)
PYGI_SCALAR (UINT64,
             GI_TYPE_TAG_UINT64,
             guint64,
             v_uint64,
             0,
             UINT64_MAX,
             PyLong_FromUnsignedLongLong,
             unsigned long long,
             1)

PYGI_SCALAR (FLOAT,
             GI_TYPE_TAG_FLOAT,
             gfloat,
             v_float,
             -G_MAXFLOAT,
             G_MAXFLOAT,
             PyFloat_FromDouble,
             double,
             0)
PYGI_SCALAR (DOUBLE,
             GI_TYPE_TAG_DOUBLE,
             gdouble,
             v_double,
             -G_MAXDOUBLE,
             G_MAXDOUBLE,
             PyFloat_FromDouble,
             double,
             0)

PYGI_SCALAR (UNICHAR,
             GI_TYPE_TAG_UNICHAR,
             gunichar,
             v_uint32,
             0,
             G_MAXUINT32,
             PyUnicode_FromOrdinal,
             int,
             0)
PYGI_SCALAR (GTYPE, GI_TYPE_TAG_GTYPE, GType, v_size, 0, G_MAXSIZE, PyLong_FromSize_t, size_t, 0)
