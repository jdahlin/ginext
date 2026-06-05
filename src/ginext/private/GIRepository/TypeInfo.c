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

#define TYPE_INFO_GETTERS(X)                                                                       \
  X (INT, type_info, get_tag, GITypeInfo)                                                          \
  X (BOOL, type_info, is_pointer, GITypeInfo)

TYPE_INFO_GETTERS (INFO_EMIT_FN)

/* get_param_type(n): element type of a container (array/list/hash). */
static PyObject *
typefn_get_param_type (PyObject *self, PyObject *arg)
{
  long n = PyLong_AsLong (arg);
  if (n == -1 && PyErr_Occurred ())
    return NULL;
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_type_info_get_param_type ((GITypeInfo *)PYGI_INFO (self), (unsigned int)n));
}

/* get_interface(): the referenced registered-type info for an INTERFACE tag
 * (object/struct/boxed/enum/flags/callback), or None. */
static PyObject *
typefn_get_interface (PyObject *self, PyObject *Py_UNUSED (a))
{
  return gi_info_to_py_owned (gi_type_info_get_interface ((GITypeInfo *)PYGI_INFO (self)));
}

/* get_array_length_index(): the arg index carrying this array's length, or -1.
 * Used to drop the implicit length companion from the Python signature. */
static PyObject *
typefn_get_array_length_index (PyObject *self, PyObject *Py_UNUSED (a))
{
  unsigned int index = 0;
  if (gi_type_info_get_array_length_index ((GITypeInfo *)PYGI_INFO (self), &index))
    return PyLong_FromUnsignedLong (index);
  return PyLong_FromLong (-1);
}

static PyMethodDef type_info_methods[]
    = { TYPE_INFO_GETTERS (INFO_EMIT_DEF){ "get_param_type", typefn_get_param_type, METH_O, NULL },
        { "get_interface", typefn_get_interface, METH_NOARGS, NULL },
        { "get_array_length_index", typefn_get_array_length_index, METH_NOARGS, NULL },
        { 0 } };

INFO_TYPE (PyGITypeInfo_Type, "TypeInfo", &PyGIBaseInfo_Type, type_info_methods, NULL);
