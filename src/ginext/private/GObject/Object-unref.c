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

/* GObject wrapper lifecycle refcount helpers. object_unref is the raw drop
 * used by GObject.__del__ (import-free, so it survives interpreter shutdown);
 * ref_count reads the ref_count field for __grefcount__; plus force_floating
 * and ref_sink.
 */
#include "common.h"
#include "Object-info.h"

static GObject *
gobject_from_py_arg (PyObject *arg)
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
py_object_unref (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source;
  if (!PyArg_ParseTuple (args, "O", &source))
    return NULL;
  GObject *obj = gobject_from_py_arg (source);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj)
    g_object_unref (obj);
  Py_RETURN_NONE;
}

PyObject *
py_object_ref_count (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source;
  if (!PyArg_ParseTuple (args, "O", &source))
    return NULL;
  GObject *obj = gobject_from_py_arg (source);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj == NULL)
    return PyLong_FromLong (0);
  return PyLong_FromUnsignedLong ((unsigned long)obj->ref_count);
}

PyObject *
py_object_force_floating (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source;
  if (!PyArg_ParseTuple (args, "O", &source))
    return NULL;
  GObject *obj = gobject_from_py_arg (source);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj)
    g_object_force_floating (obj);
  Py_RETURN_NONE;
}

PyObject *
py_object_ref_sink (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *source;
  if (!PyArg_ParseTuple (args, "O", &source))
    return NULL;
  GObject *obj = gobject_from_py_arg (source);
  if (obj == NULL && PyErr_Occurred ())
    return NULL;
  if (obj)
    g_object_ref_sink (obj);
  Py_RETURN_NONE;
}
