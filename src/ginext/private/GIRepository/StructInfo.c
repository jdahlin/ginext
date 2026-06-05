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

#define STRUCT_INFO_GETTERS(X)                                                                     \
  X (UINT, struct_info, get_n_methods, GIStructInfo)                                               \
  X (SIZE, struct_info, get_size, GIStructInfo)

STRUCT_INFO_GETTERS (INFO_EMIT_FN)

static PyMethodDef struct_info_methods[]
    = { STRUCT_INFO_GETTERS (
            INFO_EMIT_DEF){ "record_info", ginext_record_info_method, METH_NOARGS, NULL },
        { "find_method", ginext_find_method_method, METH_VARARGS, NULL },
        { "anonymous_union_offset", ginext_anonymous_union_offset_method, METH_VARARGS, NULL },
        { 0 } };

INFO_TYPE (PyGIStructInfo_Type,
           "StructInfo",
           &PyGIRegisteredTypeInfo_Type,
           struct_info_methods,
           NULL);
