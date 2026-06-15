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

/* `register_gobject_subclass(cls, annotations, type_name)` — registers a
 * new GType derived from cls.__bases__[0].gimeta.gtype, installs one
 * GParamSpec per annotated Property descriptor, and returns a GIMeta.
 *
 * The bulk of the work is the loop that pairs each annotation with the
 * matching descriptor in cls.__dict__, calls make_pspec, and accumulates
 * pspecs/prop_ids dicts. Type-name disambiguation happens up front via
 * unique_type_name so two `class Foo(GObject)` declarations don't fight
 * over the same global GType name.
 */
#include "common.h"
#include "Object-register.h"
#include "ParamSpec-make.h"
#include "Type-name.h"
#include "GIMeta.h"
#include "Object-vfunc.h"
#include "gimeta-helpers.h"

/* Steal a value into a dict (single-line OOM-safe). */
static int
dict_set_steal (PyObject *dict, PyObject *key, PyObject *value)
{
  if (!value)
    return -1;
  int rc = PyDict_SetItem (dict, key, value);
  Py_DECREF (value);
  return rc;
}

/* Resolve the first base that carries a GType. Python mixins may precede the
 * actual GObject/GInterface base in compat-style multiple inheritance. */
static PyObject *
parent_class_and_gtype (PyObject *cls, GType *out_gtype)
{
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "cls is not a type");
      return NULL;
    }
  PyObject *bases = ((PyTypeObject *)cls)->tp_bases;
  if (bases == NULL)
    {
      PyErr_SetString (PyExc_TypeError, "__bases__ is not initialized");
      return NULL;
    }
  if (!PyTuple_Check (bases))
    {
      PyErr_SetString (PyExc_TypeError, "__bases__ is not a tuple");
      return NULL;
    }
  Py_ssize_t n_bases = PyTuple_GET_SIZE (bases);
  for (Py_ssize_t i = 0; i < n_bases; i++)
    {
      PyObject *base = PyTuple_GET_ITEM (bases, i);
      PyObject *parent_cls = Py_NewRef (base);
      if (pygi_gtype_from_py_object (parent_cls, out_gtype) == 0)
        return parent_cls;
      Py_DECREF (parent_cls);
      if (!PyErr_ExceptionMatches (PyExc_AttributeError)
          && !PyErr_ExceptionMatches (PyExc_TypeError))
        return NULL;
      PyErr_Clear ();
    }

  PyErr_SetString (PyExc_TypeError, "no GType-bearing base class found");
  return NULL;
}

static int
add_declared_interfaces (PyObject *cls, PyObject *parent_cls, GType parent_gtype, GType gtype)
{
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "cls is not a type");
      return -1;
    }
  PyObject *bases = ((PyTypeObject *)cls)->tp_bases;
  if (bases == NULL)
    {
      PyErr_SetString (PyExc_TypeError, "__bases__ is not initialized");
      return -1;
    }
  if (!PyTuple_Check (bases))
    {
      PyErr_SetString (PyExc_TypeError, "__bases__ is not a tuple");
      return -1;
    }

  Py_ssize_t n_bases = PyTuple_GET_SIZE (bases);
  for (Py_ssize_t i = 0; i < n_bases; i++)
    {
      PyObject *base = PyTuple_GET_ITEM (bases, i);
      if (base == parent_cls)
        continue;
      PyObject *gimeta = NULL;
      if (pygi_object_get_gimeta (base, &gimeta) < 0)
          return -1;
      if (gimeta == NULL)
        continue;

      GType iface_gtype = G_TYPE_INVALID;
      if (pygi_gimeta_get_gtype (gimeta, &iface_gtype) < 0)
        {
          Py_DECREF (gimeta);
          return -1;
        }
      Py_DECREF (gimeta);
      if (iface_gtype == G_TYPE_INVALID)
        return -1;
      if (iface_gtype == G_TYPE_INVALID || g_type_fundamental (iface_gtype) != G_TYPE_INTERFACE
          || g_type_is_a (parent_gtype, iface_gtype) || g_type_is_a (gtype, iface_gtype))
        {
          continue;
        }

      GInterfaceInfo iface_info = { 0 };
      g_type_add_interface_static (gtype, iface_gtype, &iface_info);
    }

  return 0;
}

PyObject *
pygi_register_gobject_subclass_for_class (PyObject *cls,
                                          PyObject *annotations,
                                          const char *requested_name)
{
  g_autofree char *type_name = unique_type_name (requested_name);
  if (!type_name)
    return NULL;
  Py_AUTO_DECREF PyObject *type_name_obj = PyUnicode_FromString (type_name);
  if (!type_name_obj)
    return NULL;

  GType parent_gtype;
  Py_AUTO_DECREF PyObject *parent_cls = parent_class_and_gtype (cls, &parent_gtype);
  if (!parent_cls)
    return NULL;

  if (ginext_gobject_validate_vfunc_overrides (cls, parent_cls) < 0)
    return NULL;

  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "cls is not a type");
      return NULL;
    }
  Py_AUTO_DECREF PyObject *cls_dict = Py_XNewRef (((PyTypeObject *)cls)->tp_dict);
  Py_AUTO_DECREF PyObject *pspecs_dict = PyDict_New ();
  Py_AUTO_DECREF PyObject *prop_ids_dict = PyDict_New ();
  if (!cls_dict || !pspecs_dict || !prop_ids_dict)
    return NULL;

  /* Iterate annotations; pick up Property descriptors by duck-typing
     * on `default`. cls.__dict__ is a mappingproxy, not a real dict, so
     * use PyMapping_GetOptionalItem rather than PyDict_GetItemRef. */
  guint n_pspecs = 0, cap = 4;
  GParamSpec **pspecs = g_new (GParamSpec *, cap);

  PyObject *key, *value_type;
  Py_ssize_t pos = 0;
  while (PyDict_Next (annotations, &pos, &key, &value_type))
    {
      Py_AUTO_DECREF PyObject *prop = NULL;
      if (PyMapping_GetOptionalItem (cls_dict, key, &prop) < 0)
        goto error;
      if (!prop)
        continue;

      int has_default = PyObject_HasAttrStringWithError (prop, "default");
      if (has_default < 0)
        goto error;
      if (!has_default)
        continue;

      const char *attr_name = PyUnicode_AsUTF8 (key);
      if (!attr_name)
        goto error;

      GParamSpec *pspec = make_pspec (attr_name, value_type, prop);
      if (!pspec)
        goto error;

      if (n_pspecs == cap)
        {
          cap *= 2;
          pspecs = g_renew (GParamSpec *, pspecs, cap);
        }
      pspecs[n_pspecs++] = pspec;

      if (dict_set_steal (pspecs_dict, key, PyLong_FromVoidPtr (pspec)) < 0
          || dict_set_steal (prop_ids_dict, key, PyLong_FromUnsignedLong (n_pspecs)) < 0)
        goto error;
    }

  GTypeQuery query;
  g_type_query (parent_gtype, &query);

  ClassData *data = g_new0 (ClassData, 1);
  data->n_props = n_pspecs;
  data->pspecs = pspecs; /* ownership transfers */
  data->class_state_offset = query.class_size;

  GTypeInfo info = {
    .class_size = (guint16)(query.class_size + sizeof (ClassState)),
    .class_init = ginext_class_init,
    .class_data = data,
    .instance_size = (guint16)query.instance_size,
    .instance_init = ginext_instance_init,
  };

  GType gtype = g_type_register_static (parent_gtype, type_name, &info, 0);
  if (!gtype)
    {
      class_data_free (data); /* frees pspecs */
      PyErr_Format (PyExc_RuntimeError, "g_type_register_static failed for '%s'", type_name);
      return NULL;
    }

  if (add_declared_interfaces (cls, parent_cls, parent_gtype, gtype) < 0)
    return NULL;

  if (ginext_gobject_install_vfunc_overrides (cls, gtype, parent_cls) < 0)
    return NULL;

  return gimeta_new (gtype, type_name_obj, parent_cls, pspecs_dict, prop_ids_dict, Py_None);

error:
  for (guint i = 0; i < n_pspecs; i++)
    g_param_spec_unref (pspecs[i]);
  g_free (pspecs);
  return NULL;
}
