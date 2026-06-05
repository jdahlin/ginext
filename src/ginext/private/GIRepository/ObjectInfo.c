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

#define OBJECT_INFO_GETTERS(X)                                                                     \
  X (UINT, object_info, get_n_methods, GIObjectInfo)                                               \
  X (UINT, object_info, get_n_signals, GIObjectInfo)                                               \
  X (UINT, object_info, get_n_vfuncs, GIObjectInfo)                                                \
  X (UINT, object_info, get_n_properties, GIObjectInfo)                                            \
  X (UINT, object_info, get_n_interfaces, GIObjectInfo)                                            \
  X (BOOL, object_info, get_fundamental, GIObjectInfo)

OBJECT_INFO_GETTERS (INFO_EMIT_FN)

static PyMethodDef object_info_methods[]
    = { OBJECT_INFO_GETTERS (
            INFO_EMIT_DEF){ "object_info", ginext_object_info_method, METH_NOARGS, NULL },
        { 0 } };

INFO_TYPE (PyGIObjectInfo_Type,
           "ObjectInfo",
           &PyGIRegisteredTypeInfo_Type,
           object_info_methods,
           NULL);
