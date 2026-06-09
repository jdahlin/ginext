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

#define FIELD_INFO_GETTERS(X)                                                                      \
  X (INT, field_info, get_flags, GIFieldInfo)                                                      \
  X (INT, field_info, get_offset, GIFieldInfo)                                                     \
  X (INT, field_info, get_size, GIFieldInfo)

FIELD_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
fieldfn_get_type_info (PyObject *self, PyObject *Py_UNUSED (a))
{
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_field_info_get_type_info ((GIFieldInfo *)PYGI_INFO (self)));
}

static PyMethodDef field_info_methods[]
    = { FIELD_INFO_GETTERS (INFO_EMIT_DEF){
          "get_type_info", fieldfn_get_type_info, METH_NOARGS,
          "($self, /) -> TypeInfo\n--\n\n" },
        { 0 } };

INFO_TYPE (PyGIFieldInfo_Type,
           "FieldInfo",
           &PyGIBaseInfo_Type,
           field_info_methods,
           NULL);
