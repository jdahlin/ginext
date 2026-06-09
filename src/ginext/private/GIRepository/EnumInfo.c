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

#include "GIRepository/Info.h"
#include "GIRepository/BaseInfo.h"

#define ENUM_INFO_GETTERS(X) X (UINT, enum_info, get_n_values, GIEnumInfo)

/* get_members() → [(name, value), ...]. Returns all enum members as
 * (name_str, int_value) pairs without exposing ValueInfo objects. */
static PyObject *
enumfn_get_members (PyObject *self, PyObject *Py_UNUSED (a))
{
  GIEnumInfo *einfo = (GIEnumInfo *)PYGI_INFO (self);
  unsigned int n = gi_enum_info_get_n_values (einfo);
  PyObject *list = PyList_New ((Py_ssize_t)n);
  if (list == NULL)
    return NULL;
  for (unsigned int i = 0; i < n; i++)
    {
      GIValueInfo *value_info = gi_enum_info_get_value (einfo, i);
      const char *value_name = gi_base_info_get_name ((GIBaseInfo *)value_info);
      gint64 value = gi_value_info_get_value (value_info);
      PyObject *item = Py_BuildValue ("(sL)", value_name ? value_name : "", (long long)value);
      gi_base_info_unref ((GIBaseInfo *)value_info);
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)i, item);
    }
  return list;
}

ENUM_INFO_GETTERS (INFO_EMIT_FN)

/* get_values(): list of ValueInfo objects for each enum value. */
static PyObject *
enumfn_get_values (PyObject *self, PyObject *Py_UNUSED (a))
{
  GIEnumInfo *einfo = (GIEnumInfo *)PYGI_INFO (self);
  unsigned int n = gi_enum_info_get_n_values (einfo);
  PyObject *list = PyList_New ((Py_ssize_t)n);
  if (list == NULL)
    return NULL;
  for (unsigned int i = 0; i < n; i++)
    {
      PyObject *item = gi_info_to_py_owned ((GIBaseInfo *)gi_enum_info_get_value (einfo, i));
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)i, item);
    }
  return list;
}

static PyObject *
enumfn_is_flags (PyObject *self, PyObject *Py_UNUSED (a))
{
  /* FlagsInfo is a subtype of EnumInfo in ginext but not a separate C type.
   * Check by info type: GI_IS_FLAGS_INFO. */
  return PyBool_FromLong (GI_IS_FLAGS_INFO (PYGI_INFO (self)));
}

static PyObject *
enumfn_get_storage_type (PyObject *self, PyObject *Py_UNUSED (a))
{
  return PyLong_FromLong ((long)gi_enum_info_get_storage_type ((GIEnumInfo *)PYGI_INFO (self)));
}

static PyObject *
enumfn_get_methods (PyObject *self, PyObject *Py_UNUSED (a))
{
  GIEnumInfo *einfo = (GIEnumInfo *)PYGI_INFO (self);
  unsigned int n = gi_enum_info_get_n_methods (einfo);
  PyObject *list = PyList_New ((Py_ssize_t)n);
  if (list == NULL)
    return NULL;
  for (unsigned int i = 0; i < n; i++)
    {
      PyObject *item = gi_info_to_py_owned ((GIBaseInfo *)gi_enum_info_get_method (einfo, i));
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)i, item);
    }
  return list;
}

static PyMethodDef enum_info_extra_methods[]
    = { ENUM_INFO_GETTERS (INFO_EMIT_DEF){
          "get_members", enumfn_get_members, METH_NOARGS,
          "($self, /) -> list[tuple[str, int]]\n--\n\n" },
        { "get_values", enumfn_get_values, METH_NOARGS,
          "($self, /) -> list[BaseInfo]\n--\n\n" },
        { "is_flags", enumfn_is_flags, METH_NOARGS,
          "($self, /) -> bool\n--\n\n" },
        { "get_storage_type", enumfn_get_storage_type, METH_NOARGS,
          "($self, /) -> int\n--\n\n" },
        { "get_methods", enumfn_get_methods, METH_NOARGS,
          "($self, /) -> list[FunctionInfo]\n--\n\n" },
        { 0 } };

/* Reuse INFO_TYPE but supply our own method table (GETTERS + get_members). */
INFO_TYPE (PyGIEnumInfo_Type,
           "EnumInfo",
           &PyGIRegisteredTypeInfo_Type,
           enum_info_extra_methods,
           NULL);
