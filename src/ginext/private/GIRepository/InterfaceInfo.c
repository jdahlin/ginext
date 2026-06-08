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

#define INTERFACE_INFO_GETTERS(X)                                                                  \
  X (UINT, interface_info, get_n_methods, GIInterfaceInfo)                                         \
  X (UINT, interface_info, get_n_properties, GIInterfaceInfo)                                      \
  X (UINT, interface_info, get_n_signals, GIInterfaceInfo)                                         \
  X (UINT, interface_info, get_n_vfuncs, GIInterfaceInfo)                                          \
  X (UINT, interface_info, get_n_prerequisites, GIInterfaceInfo)

INTERFACE_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
interfacefn_get_prerequisite (PyObject *self, PyObject *arg)
{
  long n = PyLong_AsLong (arg);
  if (n == -1 && PyErr_Occurred ())
    return NULL;
  return gi_info_to_py_owned (
      gi_interface_info_get_prerequisite ((GIInterfaceInfo *)PYGI_INFO (self), (unsigned int)n));
}

static PyMethodDef interface_info_methods[]
    = { INTERFACE_INFO_GETTERS (
            INFO_EMIT_DEF){
          "get_prerequisite", interfacefn_get_prerequisite, METH_O,
          "($self, n, /) -> BaseInfo\n--\n\n" },
        { "get_n_prerequisites",
          infofn_interface_info_get_n_prerequisites,
          METH_NOARGS,
          "($self, /) -> int\n--\n\n" },
        { "object_info", ginext_object_info_method, METH_NOARGS, NULL },
        { 0 } };

INFO_TYPE (PyGIInterfaceInfo_Type,
           "InterfaceInfo",
           &PyGIRegisteredTypeInfo_Type,
           interface_info_methods,
           NULL);
