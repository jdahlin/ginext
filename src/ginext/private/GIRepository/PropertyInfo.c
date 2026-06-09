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

#define PROPERTY_INFO_GETTERS(X)                                                                   \
  X (INT, property_info, get_flags, GIPropertyInfo)                                                \
  X (INT, property_info, get_ownership_transfer, GIPropertyInfo)

PROPERTY_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
propertyfn_get_type_info (PyObject *self, PyObject *Py_UNUSED (a))
{
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_property_info_get_type_info ((GIPropertyInfo *)PYGI_INFO (self)));
}

static PyMethodDef property_info_methods[]
    = { PROPERTY_INFO_GETTERS (INFO_EMIT_DEF){
          "get_type_info", propertyfn_get_type_info, METH_NOARGS,
          "($self, /) -> TypeInfo\n--\n\n" },
        { 0 } };

INFO_TYPE (PyGIPropertyInfo_Type,
           "PropertyInfo",
           &PyGIBaseInfo_Type,
           property_info_methods,
           NULL);
