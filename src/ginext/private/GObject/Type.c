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

#include "common.h"


static GEnumValue *
build_enum_values (PyObject *members, gboolean is_flags)
{
  Py_ssize_t n = PyDict_Size (members);
  GEnumValue *values = g_new0 (GEnumValue, n + 1);
  Py_ssize_t i = 0;
  PyObject *key, *val;
  Py_ssize_t pos = 0;
  while (PyDict_Next (members, &pos, &key, &val))
    {
      const char *name = PyUnicode_AsUTF8 (key);
      if (name == NULL)
        {
          g_free (values);
          return NULL;
        }
      values[i].value = is_flags ? (gint)PyLong_AsUnsignedLong (val) : (gint)PyLong_AsLong (val);
      if (PyErr_Occurred ())
        {
          g_free (values);
          return NULL;
        }
      char *nick = g_ascii_strdown (name, -1);
      for (char *p = nick; *p; p++)
        if (*p == '_')
          *p = '-';
      values[i].value_name = g_strdup (name);
      values[i].value_nick = nick;
      i++;
    }
  return values;
}

static PyObject *
register_enum_or_flags (const char *type_name, PyObject *members, gboolean is_flags)
{
  GType existing = g_type_from_name (type_name);
  if (existing != 0)
    return PyLong_FromUnsignedLongLong ((unsigned long long)existing);

  GEnumValue *values = build_enum_values (members, is_flags);
  if (values == NULL)
    return NULL;
  GType gtype = is_flags
                    ? g_flags_register_static (type_name, (GFlagsValue *)values)
                    : g_enum_register_static (type_name, values);
  return PyLong_FromUnsignedLongLong ((unsigned long long)gtype);
}

PyObject *
py_register_static (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  unsigned long long gtype_base_raw;
  const char *type_name = NULL;
  PyObject *members = NULL;
  if (!PyArg_ParseTuple (args, "Ks|O!", &gtype_base_raw, &type_name, &PyDict_Type, &members))
    return NULL;

  GType gtype_base = (GType)gtype_base_raw;

  if (gtype_base == G_TYPE_POINTER)
    {
      GType existing = g_type_from_name (type_name);
      if (existing != 0)
        return PyLong_FromUnsignedLongLong ((unsigned long long)existing);
      return PyLong_FromUnsignedLongLong (
          (unsigned long long)g_pointer_type_register_static (type_name));
    }

  if (gtype_base == G_TYPE_ENUM || gtype_base == G_TYPE_FLAGS)
    {
      if (members == NULL)
        {
          PyErr_SetString (PyExc_TypeError, "members dict required for enum/flags");
          return NULL;
        }
      return register_enum_or_flags (type_name, members, gtype_base == G_TYPE_FLAGS);
    }

  PyErr_Format (PyExc_ValueError, "unsupported gtype_base: %llu", gtype_base_raw);
  return NULL;
}
