/* Copyright 2026 Johan Dahlin
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#pragma once

#include "marshal/conversion.h"
#include "GObject/GIMeta.h"

static inline int
pygi_object_get_gimeta (PyObject *obj, PyObject **out)
{
  return PyObject_GetOptionalAttrString (obj, "gimeta", out);
}

static inline int
pygi_gimeta_get_gtype (PyObject *gimeta, GType *out)
{
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      *out = ((GIMetaObject *)gimeta)->gtype;
      return 0;
    }

  PyObject *gtype_obj = NULL;
  if (PyObject_GetOptionalAttrString (gimeta, "gtype", &gtype_obj) < 0)
    return -1;
  if (gtype_obj == NULL)
    {
      PyErr_SetString (PyExc_AttributeError, "gimeta has no gtype");
      return -1;
    }

  unsigned long long gtype_value = PyLong_AsUnsignedLongLong (gtype_obj);
  Py_DECREF (gtype_obj);
  if (PyErr_Occurred ())
    return -1;

  *out = (GType)gtype_value;
  return 0;
}

static inline int
pygi_gimeta_get_gi_info (PyObject *gimeta, PyObject **out)
{
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      *out = Py_XNewRef (((GIMetaObject *)gimeta)->gi_info);
      return 0;
    }
  return PyObject_GetOptionalAttrString (gimeta, "gi_info", out);
}

static inline int
pygi_gimeta_get_type_name (PyObject *gimeta, PyObject **out)
{
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      *out = Py_XNewRef (((GIMetaObject *)gimeta)->type_name);
      return 0;
    }
  return PyObject_GetOptionalAttrString (gimeta, "type_name", out);
}

static inline int
pygi_gimeta_get_method_infos (PyObject *gimeta, PyObject **out)
{
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      *out = Py_XNewRef (((GIMetaObject *)gimeta)->method_infos);
      return 0;
    }
  return PyObject_GetOptionalAttrString (gimeta, "method_infos", out);
}

static inline int
pygi_gimeta_get_extensions (PyObject *gimeta, PyObject **out)
{
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      *out = Py_XNewRef (((GIMetaObject *)gimeta)->extensions);
      return 0;
    }
  return PyObject_GetOptionalAttrString (gimeta, "extensions", out);
}

static inline int
pygi_gimeta_get_profile (PyObject *gimeta, PyObject **out)
{
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      *out = Py_XNewRef (((GIMetaObject *)gimeta)->profile);
      return 0;
  }
  return PyObject_GetOptionalAttrString (gimeta, "profile", out);
}

static inline int
pygi_gimeta_get_hidden_fields (PyObject *gimeta, PyObject **out)
{
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      *out = PyObject_GetAttrString (gimeta, "hidden_fields");
      return *out == NULL ? -1 : 0;
    }
  return PyObject_GetOptionalAttrString (gimeta, "hidden_fields", out);
}
