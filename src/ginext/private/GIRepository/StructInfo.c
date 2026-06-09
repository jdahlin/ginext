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

#define STRUCT_INFO_GETTERS(X)                                                                     \
  X (UINT, struct_info, get_n_methods, GIStructInfo)                                               \
  X (SIZE, struct_info, get_size, GIStructInfo)                                                    \
  X (SIZE, struct_info, get_alignment, GIStructInfo)                                                \
  X (BOOL, struct_info, is_gtype_struct, GIStructInfo)                                             \
  X (BOOL, struct_info, is_foreign, GIStructInfo)

STRUCT_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
structfn_get_fields (PyObject *self, PyObject *Py_UNUSED (a))
{
  GIStructInfo *sinfo = (GIStructInfo *)PYGI_INFO (self);
  unsigned int n = gi_struct_info_get_n_fields (sinfo);
  PyObject *list = PyList_New ((Py_ssize_t)n);
  if (list == NULL)
    return NULL;
  for (unsigned int i = 0; i < n; i++)
    {
      PyObject *item = gi_info_to_py_owned ((GIBaseInfo *)gi_struct_info_get_field (sinfo, i));
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
structfn_find_field (PyObject *self, PyObject *arg)
{
  const char *name = PyUnicode_AsUTF8 (arg);
  if (name == NULL)
    return NULL;
  GIStructInfo *sinfo = (GIStructInfo *)PYGI_INFO (self);
  unsigned int n = gi_struct_info_get_n_fields (sinfo);
  for (unsigned int i = 0; i < n; i++)
    {
      GIFieldInfo *finfo = gi_struct_info_get_field (sinfo, i);
      const char *fname = gi_base_info_get_name ((GIBaseInfo *)finfo);
      if (fname != NULL && strcmp (fname, name) == 0)
        return gi_info_to_py_owned ((GIBaseInfo *)finfo);
      gi_base_info_unref ((GIBaseInfo *)finfo);
    }
  Py_RETURN_NONE;
}

static PyMethodDef struct_info_methods[]
    = { STRUCT_INFO_GETTERS (
            INFO_EMIT_DEF){ "record_info", ginext_record_info_method, METH_NOARGS, NULL },
        { "find_method", ginext_find_method_method, METH_VARARGS, NULL },
        { "anonymous_union_offset", ginext_anonymous_union_offset_method, METH_VARARGS, NULL },
        { "get_fields", structfn_get_fields, METH_NOARGS,
          "($self, /) -> list[FieldInfo]\n--\n\n" },
        { "find_field", structfn_find_field, METH_O,
          "($self, name, /) -> FieldInfo | None\n--\n\n" },
        { 0 } };

INFO_TYPE (PyGIStructInfo_Type,
           "StructInfo",
           &PyGIRegisteredTypeInfo_Type,
           struct_info_methods,
           NULL);
