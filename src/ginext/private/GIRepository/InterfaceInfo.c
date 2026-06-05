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

#define INTERFACE_INFO_GETTERS(X)                                                                  \
  X (UINT, interface_info, get_n_methods, GIInterfaceInfo)                                         \
  X (UINT, interface_info, get_n_properties, GIInterfaceInfo)                                      \
  X (UINT, interface_info, get_n_signals, GIInterfaceInfo)                                         \
  X (UINT, interface_info, get_n_vfuncs, GIInterfaceInfo)

INTERFACE_INFO_GETTERS (INFO_EMIT_FN)

static PyMethodDef interface_info_methods[]
    = { INTERFACE_INFO_GETTERS (
            INFO_EMIT_DEF){ "object_info", ginext_object_info_method, METH_NOARGS, NULL },
        { 0 } };

INFO_TYPE (PyGIInterfaceInfo_Type,
           "InterfaceInfo",
           &PyGIRegisteredTypeInfo_Type,
           interface_info_methods,
           NULL);
