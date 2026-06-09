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

#define VFUNC_INFO_GETTERS(X)                                                                      \
  X (INT, vfunc_info, get_flags, GIVFuncInfo)                                                      \
  X (SIZE, vfunc_info, get_offset, GIVFuncInfo)

VFUNC_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
vfuncfn_get_invoker (PyObject *self, PyObject *Py_UNUSED (a))
{
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_vfunc_info_get_invoker ((GIVFuncInfo *)PYGI_INFO (self)));
}

static PyObject *
vfuncfn_get_signal (PyObject *self, PyObject *Py_UNUSED (a))
{
  return gi_info_to_py_owned (
      (GIBaseInfo *)gi_vfunc_info_get_signal ((GIVFuncInfo *)PYGI_INFO (self)));
}

static PyMethodDef vfunc_info_methods[]
    = { VFUNC_INFO_GETTERS (INFO_EMIT_DEF){
          "get_invoker", vfuncfn_get_invoker, METH_NOARGS,
          "($self, /) -> FunctionInfo | None\n--\n\n" },
        { "get_signal", vfuncfn_get_signal, METH_NOARGS,
          "($self, /) -> SignalInfo | None\n--\n\n" },
        { 0 } };

INFO_TYPE (PyGIVFuncInfo_Type, "VFuncInfo", &PyGICallableInfo_Type, vfunc_info_methods, NULL);
