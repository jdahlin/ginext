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

#pragma once

#include <Python.h>

PyObject *
py_record_info (PyObject *module, PyObject *args);

PyObject *
py_record_find_method (PyObject *module, PyObject *args);

/* GIRepository.StructInfo.anonymous_union_offset — given the name of the
 * field that precedes an anonymous union and an alignment hint, returns the
 * byte offset at which the anonymous union begins.
 * Arguments: (GIRepository.StructInfo|UnionInfo, field_name: str, align: int) */
PyObject *
py_girepository_struct_info_anonymous_union_offset (PyObject *module, PyObject *args);
