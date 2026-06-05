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
#include "marshal/scalar.h"

#include <girepository/girepository.h>
#include <string.h>

/* Marshal a GIConstantInfo's value to a Python object. */
PyObject *
ginext_constant_info_value (GIConstantInfo *cinfo)
{
  g_autoptr (GITypeInfo) type_info = gi_constant_info_get_type_info (cinfo);
  GIArgument value;
  memset (&value, 0, sizeof (value));
  gi_constant_info_get_value (cinfo, &value);

  PyObject *result = NULL;
  GITypeTag tag = gi_type_info_get_tag (type_info);
  switch (tag)
    {
#define PYGI_SCALAR PYGI_SCALAR_SET_RESULT_FROM_VALUE

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      result
          = value.v_string ? PyUnicode_FromString (value.v_string) : (Py_INCREF (Py_None), Py_None);
      break;
    default:
      PyErr_Format (PyExc_NotImplementedError, "constant type tag %d not supported", (int)tag);
      break;
    }

  gi_constant_info_free_value (cinfo, &value);
  return result;
}

static PyObject *
constantfn_get_value (PyObject *self, PyObject *Py_UNUSED (a))
{
  return ginext_constant_info_value ((GIConstantInfo *)PYGI_INFO (self));
}

static PyMethodDef constant_info_methods[]
    = { { "get_value", constantfn_get_value, METH_NOARGS,
          "($self, /) -> object\n--\n\n" },
        { 0 } };

INFO_TYPE (PyGIConstantInfo_Type,
           "ConstantInfo",
           &PyGIBaseInfo_Type,
           constant_info_methods,
           NULL);
