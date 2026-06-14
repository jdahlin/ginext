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
#include "GObject/Object-info.h"
#include "Value.h"
#include "gimeta-helpers.h"
#include "marshal/gvalue.h"

G_DEFINE_AUTOPTR_CLEANUP_FUNC (GObjectClass, g_type_class_unref)

typedef struct
{
  Py_ssize_t n_values;
  const char **names;
  GValue *values;
  char **owned_names;
} ConstructProperties;

static void
construct_properties_clear (ConstructProperties *props)
{
  if (props->values != NULL)
    {
      for (Py_ssize_t i = 0; i < props->n_values; i++)
        {
          if (G_IS_VALUE (&props->values[i]))
            g_value_unset (&props->values[i]);
        }
    }
  if (props->owned_names != NULL)
    {
      for (Py_ssize_t i = 0; i < props->n_values; i++)
        g_free (props->owned_names[i]);
    }
  g_free (props->owned_names);
  g_free (props->values);
  g_free ((gpointer)props->names);
}

G_DEFINE_AUTO_CLEANUP_CLEAR_FUNC (ConstructProperties, construct_properties_clear)

static char *
normalized_property_name (PyObject *py_name)
{
  const char *name = PyUnicode_AsUTF8 (py_name);
  if (name == NULL)
    return NULL;

  char *normalized = g_strdup (name);
  if (normalized == NULL)
    {
      PyErr_NoMemory ();
      return NULL;
    }
  for (char *p = normalized; *p; p++)
    {
      if (*p == '_')
        *p = '-';
    }
  return normalized;
}

/* Construct a GObject of `gtype` from a properties dict, returning a new owned
 * reference (NULL on error). Property names are normalized foo_bar -> foo-bar.
 * This is the C core shared by the py_construct_gobject module function and the
 * GObject tp_init (which uses it without boxing the pointer through a PyLong). */
GObject *
pygi_construct_gobject_object (GType gtype, PyObject *kwargs)
{
  if (!g_type_is_a (gtype, G_TYPE_OBJECT))
    {
      PyErr_Format (PyExc_TypeError, "%s is not a GObject type", g_type_name (gtype));
      return NULL;
    }
  if (G_TYPE_IS_ABSTRACT (gtype))
    {
      PyErr_Format (PyExc_TypeError,
                    "cannot construct abstract GObject type %s",
                    g_type_name (gtype));
      return NULL;
    }
  g_autoptr (GObjectClass) klass = G_OBJECT_CLASS (g_type_class_ref (gtype));
  if (klass == NULL)
    {
      PyErr_Format (PyExc_RuntimeError,
                    "could not load class for GObject type %s",
                    g_type_name (gtype));
      return NULL;
    }

  Py_ssize_t n_props = PyDict_GET_SIZE (kwargs);
  Py_ssize_t n_alloc = n_props ? n_props : 1;
  g_auto (ConstructProperties) props = {
    .n_values = n_props,
    .names = g_new0 (const char *, n_alloc),
    .values = g_new0 (GValue, n_alloc),
    .owned_names = g_new0 (char *, n_alloc),
  };

  PyObject *py_name = NULL;
  PyObject *py_value = NULL;
  Py_ssize_t pos = 0;
  Py_ssize_t i = 0;
  while (PyDict_Next (kwargs, &pos, &py_name, &py_value))
    {
      if (!PyUnicode_Check (py_name))
        {
          PyErr_SetString (PyExc_TypeError, "property names must be strings");
          return NULL;
        }

      g_autofree char *name = normalized_property_name (py_name);
      if (name == NULL)
        return NULL;

      GParamSpec *pspec = g_object_class_find_property (klass, name);
      if (pspec == NULL)
        {
          PyErr_Format (PyExc_TypeError,
                        "%s has no construct property %s",
                        g_type_name (gtype),
                        name);
          return NULL;
        }
      if ((pspec->flags & G_PARAM_WRITABLE) == 0)
        {
          PyErr_Format (PyExc_TypeError, "%s.%s is not writable", g_type_name (gtype), name);
          return NULL;
        }

      if (pygi_py_to_gvalue_targeted (pspec->value_type, py_value, &props.values[i], name) < 0)
        {
          if (PyErr_ExceptionMatches (PyExc_NotImplementedError))
            {
              PyErr_Clear ();
              PyErr_Format (PyExc_TypeError,
                            "%s.%s cannot be set from %.200s",
                            g_type_name (gtype),
                            name,
                            Py_TYPE (py_value)->tp_name);
            }
          return NULL;
        }

      props.names[i] = name;
      props.owned_names[i] = g_steal_pointer (&name);
      i++;
    }

  g_autoptr (GObject) obj
      = g_object_new_with_properties (gtype, (guint)n_props, props.names, props.values);
  if (obj == NULL)
    {
      PyErr_Format (PyExc_RuntimeError,
                    "g_object_new_with_properties failed for GType %s",
                    g_type_name (gtype));
      return NULL;
    }
  if (G_IS_INITIALLY_UNOWNED (obj))
    g_object_ref_sink (obj);

  return g_steal_pointer (&obj);
}

PyObject *
py_construct_gobject (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  PyObject *kwargs = NULL;
  if (!PyArg_ParseTuple (args, "OO!", &gtype_obj, &PyDict_Type, &kwargs))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;

  GObject *obj = pygi_construct_gobject_object (gtype, kwargs);
  if (obj == NULL)
    return NULL;
  return pygi_gobject_to_py_as_gtype (obj, gtype, GI_TRANSFER_EVERYTHING);
}
