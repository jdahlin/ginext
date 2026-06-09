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

#define REGISTERED_TYPE_INFO_GETTERS(X)                                                            \
  X (STR, registered_type_info, get_type_name, GIRegisteredTypeInfo)                               \
  X (GTYPE, registered_type_info, get_g_type, GIRegisteredTypeInfo)

REGISTERED_TYPE_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
registeredfn_get_type_init (PyObject *self, PyObject *Py_UNUSED (a))
{
  const char *s
      = gi_registered_type_info_get_type_init_function_name ((GIRegisteredTypeInfo *)PYGI_INFO (self));
  return PyUnicode_FromString (s ? s : "");
}

static PyMethodDef registered_type_info_methods[]
    = { REGISTERED_TYPE_INFO_GETTERS (INFO_EMIT_DEF){
          "get_type_init", registeredfn_get_type_init, METH_NOARGS,
          "($self, /) -> str\n--\n\n" },
        { 0 } };

INFO_TYPE (PyGIRegisteredTypeInfo_Type,
           "RegisteredTypeInfo",
           &PyGIBaseInfo_Type,
           registered_type_info_methods,
           NULL);
