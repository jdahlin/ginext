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
#include "Object-info.h"
#include <weakrefobject.h>

static GObject *
gobject_from_wrapper_or_pointer (PyObject *arg)
{
  GObject *obj = pygi_gobject_get (arg);
  if (obj != NULL)
    return obj;
  if (!PyErr_ExceptionMatches (PyExc_AttributeError))
    return NULL;
  PyErr_Clear ();
  if (!PyLong_Check (arg))
    return NULL;
  obj = (GObject *)PyLong_AsVoidPtr (arg);
  if (PyErr_Occurred ())
    return NULL;
  return obj;
}

PyObject *
py_gobject_wrapper_get (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  GObject *obj = gobject_from_wrapper_or_pointer (ptr_obj);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj == NULL)
    Py_RETURN_NONE;
  if (!G_IS_OBJECT (obj))
    {
      PyErr_SetString (PyExc_TypeError, "pointer is not a GObject");
      return NULL;
    }

  PyObject *wrapper = pygi_gobject_wrapper_ref (obj);
  if (wrapper == NULL)
    {
      if (PyErr_Occurred ())
        return NULL;
      Py_RETURN_NONE;
    }

  return wrapper;
}

PyObject *
py_object_is_bound (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &obj))
    return NULL;

  gboolean bound = FALSE;
  int local_status = pygi_gobject_wrapper_local_bound (obj, &bound);
  if (local_status < 0)
    return NULL;
  if (local_status > 0)
    return PyBool_FromLong (bound);

  if (pygi_gobject_get (obj) != NULL)
    Py_RETURN_TRUE;
  if (PyErr_ExceptionMatches (PyExc_AttributeError))
    {
      PyErr_Clear ();
      Py_RETURN_FALSE;
    }
  return NULL;
}

PyObject *
py_gobject_wrapper_set (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  PyObject *wrapper = NULL;
  if (!PyArg_ParseTuple (args, "OO", &ptr_obj, &wrapper))
    return NULL;

  GObject *obj = gobject_from_wrapper_or_pointer (ptr_obj);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj == NULL)
    {
      PyErr_SetString (PyExc_ValueError, "GObject pointer is NULL");
      return NULL;
    }

  if (pygi_gobject_wrapper_store (obj, wrapper) < 0)
    return NULL;
  Py_RETURN_NONE;
}

PyObject *
py_gobject_wrapper_clear (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  GObject *obj = gobject_from_wrapper_or_pointer (ptr_obj);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj == NULL)
    {
      PyErr_SetString (PyExc_ValueError, "GObject pointer is NULL");
      return NULL;
    }

  pygi_gobject_wrapper_clear (obj);
  Py_RETURN_NONE;
}

PyObject *
py_gobject_wrapper_owns_ref (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  gboolean owns_ref = TRUE;
  int local_status = pygi_gobject_wrapper_local_owns_ref (ptr_obj, &owns_ref);
  if (local_status < 0)
    return NULL;
  if (local_status > 0)
    return PyBool_FromLong (owns_ref);

  GObject *obj = gobject_from_wrapper_or_pointer (ptr_obj);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj == NULL)
    {
      PyErr_SetString (PyExc_ValueError, "GObject pointer is NULL");
      return NULL;
    }
  if (!G_IS_OBJECT (obj))
    {
      PyErr_SetString (PyExc_TypeError, "pointer is not a GObject");
      return NULL;
    }

  if (pygi_gobject_wrapper_owns_ref (obj))
    Py_RETURN_TRUE;
  Py_RETURN_FALSE;
}

PyObject *
py_gobject_wrapper_set_owns_ref (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  int owns_ref = 0;
  if (!PyArg_ParseTuple (args, "Op", &ptr_obj, &owns_ref))
    return NULL;

  GObject *obj = gobject_from_wrapper_or_pointer (ptr_obj);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj == NULL)
    {
      PyErr_SetString (PyExc_ValueError, "GObject pointer is NULL");
      return NULL;
    }
  if (!G_IS_OBJECT (obj))
    {
      PyErr_SetString (PyExc_TypeError, "pointer is not a GObject");
      return NULL;
    }

  pygi_gobject_wrapper_set_owns_ref (obj, owns_ref);
  pygi_gobject_wrapper_local_set_owns_ref (ptr_obj, owns_ref);
  Py_RETURN_NONE;
}
