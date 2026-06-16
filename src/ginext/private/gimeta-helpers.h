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
pygi_gimeta_get_extensions (PyObject *gimeta, PyObject **out)
{
  if (!PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      PyErr_SetString (PyExc_TypeError, "gimeta must be a GIMeta");
      return -1;
    }
  *out = Py_XNewRef (((GRegisteredTypeMetaObject *)gimeta)->extensions);
  return 0;
}

static inline int
pygi_gimeta_method_infos_contains (PyObject *gimeta, const char *name)
{
  if (PyObject_TypeCheck (gimeta, &GIMetaType))
    {
      GinextObjectMetaTable *table = &((GRegisteredTypeMetaObject *)gimeta)->method_infos;
      for (Py_ssize_t i = 0; i < table->len; i++)
        {
          if (strcmp (table->items[i].name, name) == 0)
            return 1;
        }
      return 0;
    }

  PyObject *method_infos = NULL;
  if (PyObject_GetOptionalAttrString (gimeta, "method_infos", &method_infos) < 0)
    return -1;
  if (method_infos == NULL)
    return 0;
  int contains = PyMapping_HasKeyString (method_infos, name);
  Py_DECREF (method_infos);
  return contains;
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
