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

#define ARG_INFO_GETTERS(X)                                                                        \
  X (INT, arg_info, get_direction, GIArgInfo)                                                      \
  X (BOOL, arg_info, may_be_null, GIArgInfo)                                                       \
  X (BOOL, arg_info, is_optional, GIArgInfo)

ARG_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
argfn_get_type_info (PyObject *self, PyObject *Py_UNUSED (a))
{
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_arg_info_get_type_info ((GIArgInfo *)PYGI_INFO (self)));
}

/* The arg index of this arg's closure (user_data) companion, or -1. */
static PyObject *
argfn_get_closure_index (PyObject *self, PyObject *Py_UNUSED (a))
{
  unsigned int index = 0;
  if (gi_arg_info_get_closure_index ((GIArgInfo *)PYGI_INFO (self), &index))
    return PyLong_FromUnsignedLong (index);
  return PyLong_FromLong (-1);
}

/* The arg index of this arg's destroy-notify companion, or -1. */
static PyObject *
argfn_get_destroy_index (PyObject *self, PyObject *Py_UNUSED (a))
{
  unsigned int index = 0;
  if (gi_arg_info_get_destroy_index ((GIArgInfo *)PYGI_INFO (self), &index))
    return PyLong_FromUnsignedLong (index);
  return PyLong_FromLong (-1);
}

static PyMethodDef arg_info_methods[]
    = { ARG_INFO_GETTERS (INFO_EMIT_DEF){ "get_type_info", argfn_get_type_info, METH_NOARGS, NULL },
        { "get_closure_index", argfn_get_closure_index, METH_NOARGS, NULL },
        { "get_destroy_index", argfn_get_destroy_index, METH_NOARGS, NULL },
        { 0 } };

INFO_TYPE (PyGIArgInfo_Type, "ArgInfo", &PyGIBaseInfo_Type, arg_info_methods, NULL);
