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

#include "GIRepository/BaseInfo.h"
#include "GIRepository/Info.h"

GIBaseInfo *
gi_info_from_py (PyObject *obj)
{
  if (PyObject_TypeCheck (obj, &PyGIBaseInfo_Type))
    return PYGI_INFO (obj);
  PyErr_Format (PyExc_TypeError, "expected GIBaseInfo, got %.200s", Py_TYPE (obj)->tp_name);
  return NULL;
}

GIBaseInfo *
gi_info_from_py_or_none (PyObject *obj)
{
  if (obj == NULL || obj == Py_None)
    return NULL;
  return gi_info_from_py (obj);
}

PyObject *
gi_info_to_py (GIBaseInfo *info)
{
  /* Wrap as a native GIRepository.*Info type. pygi_base_info_wrap takes its
   * own ref and maps NULL to None. */
  return pygi_base_info_wrap (info);
}

PyObject *
gi_info_to_py_owned (GIBaseInfo *info)
{
  PyObject *obj = pygi_base_info_wrap (info);
  if (info != NULL)
    gi_base_info_unref (info);
  return obj;
}

/* ── BaseInfo type ───────────────────────────────────────────────────────────
 *
 * Root of the hierarchy. Defines the shared dealloc / tp_new / repr that every
 * subtype inherits via tp_base, plus the get_name / get_namespace getters and
 * the name / namespace convenience properties. */

#define BASE_INFO_GETTERS(X)                                                                       \
  X (STR, base_info, get_name, GIBaseInfo)                                                         \
  X (STR, base_info, get_namespace, GIBaseInfo)

BASE_INFO_GETTERS (INFO_EMIT_FN)

static PyObject *
info_tp_new (PyTypeObject *type, PyObject *Py_UNUSED (args), PyObject *Py_UNUSED (kwds))
{
  PyErr_Format (PyExc_TypeError, "cannot create %.200s instances", type->tp_name);
  return NULL;
}

void
ginext_info_dealloc (PyObject *self)
{
  GIBaseInfo *info = PYGI_INFO (self);
  if (info != NULL)
    gi_base_info_unref (info);
  Py_TYPE (self)->tp_free (self);
}

static PyObject *
info_repr (PyObject *self)
{
  GIBaseInfo *info = PYGI_INFO (self);
  const char *ns = gi_base_info_get_namespace (info);
  const char *name = gi_base_info_get_name (info);
  return PyUnicode_FromFormat ("<%s %s.%s>",
                               Py_TYPE (self)->tp_name,
                               ns ? ns : "?",
                               name ? name : "?");
}

static PyMethodDef base_info_methods[] = { BASE_INFO_GETTERS (INFO_EMIT_DEF){ 0 } };

PyTypeObject PyGIBaseInfo_Type = {
  PyVarObject_HEAD_INIT (NULL, 0).tp_name = "ginext.GIRepository.BaseInfo",
  .tp_basicsize = sizeof (PyGIBaseInfo),
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .tp_new = info_tp_new,
  .tp_dealloc = ginext_info_dealloc,
  .tp_repr = info_repr,
  .tp_methods = base_info_methods,
};
