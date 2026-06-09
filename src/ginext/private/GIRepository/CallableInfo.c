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

#define CALLABLE_INFO_GETTERS(X)                                                                   \
  X (BOOL, callable_info, is_method, GICallableInfo)                                               \
  X (BOOL, callable_info, is_async, GICallableInfo)                                                \
  X (UINT, callable_info, get_n_args, GICallableInfo)                                              \
  X (BOOL, callable_info, may_return_null, GICallableInfo)                                         \
  X (BOOL, callable_info, skip_return, GICallableInfo)                                             \
  X (BOOL, callable_info, can_throw_gerror, GICallableInfo)                                        \
  X (INT, callable_info, get_caller_owns, GICallableInfo)

CALLABLE_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
callablefn_get_arg (PyObject *self, PyObject *arg)
{
  long n = PyLong_AsLong (arg);
  if (n == -1 && PyErr_Occurred ())
    return NULL;
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_callable_info_get_arg ((GICallableInfo *)PYGI_INFO (self), (unsigned int)n));
}

static PyObject *
callablefn_get_return_type (PyObject *self, PyObject *Py_UNUSED (a))
{
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_callable_info_get_return_type ((GICallableInfo *)PYGI_INFO (self)));
}

static PyObject *
callablefn_get_arg_names (PyObject *self, PyObject *Py_UNUSED (a))
{
  return ginext_callable_info_arg_names ((GICallableInfo *)PYGI_INFO (self));
}

static PyObject *
callablefn_get_has_user_data_slot (PyObject *self, PyObject *Py_UNUSED (a))
{
  return ginext_callable_info_has_user_data_slot ((GICallableInfo *)PYGI_INFO (self));
}

/* get_return_attribute(name): returns the attribute value or raises AttributeError. */
static PyObject *
callablefn_get_return_attribute (PyObject *self, PyObject *arg)
{
  const char *name = PyUnicode_AsUTF8 (arg);
  if (name == NULL)
    return NULL;
  const char *val
      = gi_callable_info_get_return_attribute ((GICallableInfo *)PYGI_INFO (self), name);
  if (val == NULL)
    {
      PyErr_Format (PyExc_AttributeError, "no return attribute '%s'", name);
      return NULL;
    }
  return PyUnicode_FromString (val);
}

static PyMethodDef callable_info_methods[]
    = { CALLABLE_INFO_GETTERS (INFO_EMIT_DEF){
          "get_arg", callablefn_get_arg, METH_O,
          "($self, n, /) -> BaseInfo\n--\n\n" },
        { "get_return_type", callablefn_get_return_type, METH_NOARGS,
          "($self, /) -> TypeInfo\n--\n\n" },
        { "get_arg_names", callablefn_get_arg_names, METH_NOARGS,
          "($self, /) -> list[str]\n--\n\n" },
        { "get_has_user_data_slot", callablefn_get_has_user_data_slot, METH_NOARGS,
          "($self, /) -> bool\n--\n\n" },
        { "get_return_attribute", callablefn_get_return_attribute, METH_O,
          "($self, name, /) -> str\n--\n\n" },
        { 0 } };

INFO_TYPE (PyGICallableInfo_Type,
           "CallableInfo",
           &PyGIBaseInfo_Type,
           callable_info_methods,
           NULL);
