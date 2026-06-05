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

static PyMethodDef enum_info_extra_methods[]
    = { ENUM_INFO_GETTERS (INFO_EMIT_DEF){
          "get_members", enumfn_get_members, METH_NOARGS,
          "($self, /) -> list[tuple[str, int]]\n--\n\n" },
        { 0 } };

/* Reuse INFO_TYPE but supply our own method table (GETTERS + get_members). */
INFO_TYPE (PyGIEnumInfo_Type,
           "EnumInfo",
           &PyGIRegisteredTypeInfo_Type,
           enum_info_extra_methods,
           NULL);
