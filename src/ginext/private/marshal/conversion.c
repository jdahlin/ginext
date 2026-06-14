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

#include "marshal/conversion.h"
#include "GObject/GIMeta.h"

int
pygi_gtype_from_gimeta_attr (PyObject *obj, GType *out)
{
  PyObject *type_obj = PyType_Check (obj) ? Py_NewRef (obj) : Py_NewRef ((PyObject *)Py_TYPE (obj));
  PyObject *gimeta = PyObject_GetAttrString (type_obj, "gimeta");
  Py_DECREF (type_obj);
  if (gimeta == NULL)
    return -1;

  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      *out = ((GIMetaObject *)gimeta)->gtype;
      Py_DECREF (gimeta);
      return 0;
    }

  PyObject *gtype_obj = PyObject_GetAttrString (gimeta, "gtype");
  Py_DECREF (gimeta);
  if (gtype_obj == NULL)
    return -1;

  unsigned long long gtype_value = PyLong_AsUnsignedLongLong (gtype_obj);
  Py_DECREF (gtype_obj);
  if (PyErr_Occurred ())
    return -1;

  *out = (GType)gtype_value;
  return 0;
}

int
pygi_gtype_from_py_object (PyObject *obj, GType *out)
{
  if (pygi_gtype_from_gimeta_attr (obj, out) == 0)
    return 0;
  if (!PyErr_ExceptionMatches (PyExc_AttributeError))
    return -1;
  PyErr_Clear ();

  PyObject *py_gtype = PyObject_GetAttrString (obj, "__gtype__");
  if (py_gtype != NULL)
    {
      if (pygi_gtype_from_py_object (py_gtype, out) == 0)
        {
          Py_DECREF (py_gtype);
          return 0;
        }
      Py_DECREF (py_gtype);
      return -1;
    }
  if (!PyErr_ExceptionMatches (PyExc_AttributeError))
    return -1;
  PyErr_Clear ();

  if (PyType_Check (obj))
    {
      if (obj == (PyObject *)&PyLong_Type)
        {
          *out = G_TYPE_INT;
          return 0;
        }
      if (obj == (PyObject *)&PyBool_Type)
        {
          *out = G_TYPE_BOOLEAN;
          return 0;
        }
      if (obj == (PyObject *)&PyFloat_Type)
        {
          *out = G_TYPE_DOUBLE;
          return 0;
        }
      if (obj == (PyObject *)&PyUnicode_Type)
        {
          *out = G_TYPE_STRING;
          return 0;
        }
      if (obj == (PyObject *)&PyBaseObject_Type)
        {
          *out = g_type_from_name ("PyObject");
          return 0;
        }
    }

  unsigned long long value = PyLong_AsUnsignedLongLong (obj);
  if (value == (unsigned long long)-1 && PyErr_Occurred ())
    return -1;
  *out = (GType)value;
  return 0;
}

PyGIValue
pygi_value_for_giarg (const PyGIType *type, GIArgument *arg)
{
  return (PyGIValue){
    .type = type,
    .storage = PYGI_VALUE_STORAGE_GIARG,
    .as.giarg = arg,
  };
}

PyGIValue
pygi_value_for_gvalue (const PyGIType *type, GValue *value)
{
  return (PyGIValue){
    .type = type,
    .storage = PYGI_VALUE_STORAGE_GVALUE,
    .as.gvalue = value,
  };
}

PyGIValue
pygi_value_for_memory (const PyGIType *type, void *memory)
{
  return (PyGIValue){
    .type = type,
    .storage = PYGI_VALUE_STORAGE_MEMORY,
    .as.memory = memory,
  };
}
