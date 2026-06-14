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

#include "common.h"
#include "GObject/coercions.h"

/* PyDict mapping PyLong(GType) → callable.  NULL until pygi_coercions_init. */
static PyObject *_coercions = NULL;

int
pygi_coercions_init (void)
{
  _coercions = PyDict_New ();
  return _coercions != NULL ? 0 : -1;
}

int
pygi_coercion_register (GType gtype, PyObject *fn)
{
  if (_coercions == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "coercions dict not initialised");
      return -1;
    }
  PyObject *key = PyLong_FromUnsignedLong ((gulong)gtype);
  if (key == NULL)
    return -1;
  int rc = PyDict_SetItem (_coercions, key, fn);
  Py_DECREF (key);
  return rc;
}

PyObject *
pygi_call_coercion (GType gtype, PyObject *obj)
{
  if (_coercions == NULL)
    return NULL;
  PyObject *key = PyLong_FromUnsignedLong ((gulong)gtype);
  if (key == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  PyObject *fn = PyDict_GetItemWithError (_coercions, key);
  Py_DECREF (key);
  if (fn == NULL)
    return NULL;
  return PyObject_CallOneArg (fn, obj);
}
