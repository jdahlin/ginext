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

#include <glib.h>

PyObject *
pygi_error_to_py (GIArgument *arg, GITransfer transfer);

int
pygi_error_from_py (PyObject *obj, GError **out_error);

static inline void
pygi_raise_gerror (GError *error)
{
  if (error == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "unknown GError");
      return;
    }

  const char *message = error->message != NULL ? error->message : "";
  PyObject *module = PyImport_ImportModule ("ginext.errors");
  if (module != NULL)
    {
      PyObject *factory = PyObject_GetAttrString (module, "_exception_from_gerror");
      Py_DECREF (module);
      if (factory != NULL)
        {
          PyObject *instance = PyObject_CallFunction (factory,
                                                      "kis",
                                                      (unsigned long)error->domain,
                                                      error->code,
                                                      message);
          Py_DECREF (factory);
          if (instance != NULL)
            {
              PyErr_SetObject ((PyObject *)Py_TYPE (instance), instance);
              Py_DECREF (instance);
            }
        }
    }

  if (!PyErr_Occurred ())
    PyErr_SetString (PyExc_RuntimeError, message[0] != 0 ? message : "GError");
  g_error_free (error);
}
