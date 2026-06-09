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

#define FUNCTION_INFO_GETTERS(X)                                                                   \
  X (STR, function_info, get_symbol, GIFunctionInfo)                                               \
  X (INT, function_info, get_flags, GIFunctionInfo)

FUNCTION_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
functionfn_is_constructor (PyObject *self, PyObject *Py_UNUSED (a))
{
  GIFunctionInfoFlags flags = gi_function_info_get_flags ((GIFunctionInfo *)PYGI_INFO (self));
  return PyBool_FromLong (flags & GI_FUNCTION_IS_CONSTRUCTOR);
}

static PyObject *
functionfn_is_method (PyObject *self, PyObject *Py_UNUSED (a))
{
  GIFunctionInfoFlags flags = gi_function_info_get_flags ((GIFunctionInfo *)PYGI_INFO (self));
  return PyBool_FromLong (flags & GI_FUNCTION_IS_METHOD);
}

static PyObject *
functionfn_get_finish_func (PyObject *self, PyObject *Py_UNUSED (a))
{
  GIFunctionInfo *info = (GIFunctionInfo *)PYGI_INFO (self);
  GICallableInfo *finish = gi_callable_info_get_finish_function ((GICallableInfo *)info);
  if (finish == NULL)
    Py_RETURN_NONE;
  return gi_info_to_py_owned ((GIBaseInfo *)finish);
}

static PyObject *
functionfn_get_vfunc (PyObject *self, PyObject *Py_UNUSED (a))
{
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_function_info_get_vfunc ((GIFunctionInfo *)PYGI_INFO (self)));
}

static PyMethodDef function_info_methods[]
    = { FUNCTION_INFO_GETTERS (INFO_EMIT_DEF){
          "is_constructor", functionfn_is_constructor, METH_NOARGS,
          "($self, /) -> bool\n--\n\n" },
        { "is_method", functionfn_is_method, METH_NOARGS,
          "($self, /) -> bool\n--\n\n" },
        { "get_finish_func", functionfn_get_finish_func, METH_NOARGS,
          "($self, /) -> FunctionInfo | None\n--\n\n" },
        { "get_vfunc", functionfn_get_vfunc, METH_NOARGS,
          "($self, /) -> VFuncInfo | None\n--\n\n" },
        { 0 } };

INFO_TYPE (PyGIFunctionInfo_Type,
           "FunctionInfo",
           &PyGICallableInfo_Type,
           function_info_methods,
           NULL);
