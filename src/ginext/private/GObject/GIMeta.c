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

/* GIMeta — one Python heap object per registered ginext GObject class.
 *
 * The previous dataclass-based GIMeta is replaced by this C type to avoid the
 * dict-serialize/dataclass-construct trip on every registered subclass. Keep
 * this object as a metadata view; behavior that acts on instances or signals
 * belongs on those APIs, with GIMeta only providing the state they need.
 */
#include "GIMeta.h"
#include "../GIRepository/ObjectInfo.h"
#include "Object-info.h"
#include "Object-register.h"
#include "vfunc-descr.h"
#include "ParamSpec.h"
#include "Value.h"
#include "marshal/gvalue.h"
#include "runtime/module_funcs.h"

static inline GRegisteredTypeMetaObject *
registered_meta (GIMetaObject *self)
{
  return (GRegisteredTypeMetaObject *)self;
}

static void
property_table_clear (GRegisteredTypeMetaObject *self)
{
  if (self->properties == NULL)
    return;
  for (Py_ssize_t i = 0; i < self->n_properties; i++)
    g_free (self->properties[i].name);
  g_free (self->properties);
  self->properties = NULL;
  self->n_properties = 0;
}

static int
property_table_set_from_dicts (GRegisteredTypeMetaObject *self,
                               PyObject *pspecs,
                               PyObject *prop_ids)
{
  Py_ssize_t n = PyDict_Size (pspecs);
  if (n < 0)
    return -1;
  if (n == 0)
    return 0;

  GinextPropertyMeta *items = g_new0 (GinextPropertyMeta, (gsize)n);
  PyObject *key = NULL;
  PyObject *pspec_long = NULL;
  Py_ssize_t pos = 0;
  Py_ssize_t index = 0;
  while (PyDict_Next (pspecs, &pos, &key, &pspec_long))
    {
      const char *name = PyUnicode_AsUTF8 (key);
      if (name == NULL)
        goto error;
      PyObject *prop_id_long = PyDict_GetItem (prop_ids, key);
      if (prop_id_long == NULL)
        {
          PyErr_Format (PyExc_RuntimeError,
                        "gimeta has pspec but no prop_id for %R",
                        key);
          goto error;
        }
      GParamSpec *pspec = (GParamSpec *)PyLong_AsVoidPtr (pspec_long);
      long prop_id = PyLong_AsLong (prop_id_long);
      if (PyErr_Occurred ())
        goto error;
      items[index].name = g_strdup (name);
      items[index].pspec = pspec;
      items[index].prop_id = (guint)prop_id;
      index++;
    }

  self->properties = items;
  self->n_properties = n;
  return 0;

error:
  for (Py_ssize_t i = 0; i < index; i++)
    g_free (items[i].name);
  g_free (items);
  return -1;
}

static GinextPropertyMeta *
property_table_lookup (GRegisteredTypeMetaObject *self, const char *name)
{
  for (Py_ssize_t i = 0; i < self->n_properties; i++)
    {
      if (strcmp (self->properties[i].name, name) == 0)
        return &self->properties[i];
    }
  return NULL;
}

static void
object_table_clear (GinextObjectMetaTable *table)
{
  if (table->items == NULL)
    return;
  for (Py_ssize_t i = 0; i < table->len; i++)
    {
      g_free (table->items[i].name);
      Py_XDECREF (table->items[i].value);
    }
  g_free (table->items);
  table->items = NULL;
  table->len = 0;
}

static GinextObjectMeta *
object_table_lookup (GinextObjectMetaTable *table, const char *name)
{
  for (Py_ssize_t i = 0; i < table->len; i++)
    {
      if (strcmp (table->items[i].name, name) == 0)
        return &table->items[i];
    }
  return NULL;
}

static int
object_table_set_item (GinextObjectMetaTable *table, const char *name, PyObject *value)
{
  GinextObjectMeta *existing = object_table_lookup (table, name);
  if (existing != NULL)
    {
      Py_INCREF (value);
      Py_SETREF (existing->value, value);
      return 0;
    }

  GinextObjectMeta *items = g_renew (GinextObjectMeta, table->items, (gsize)table->len + 1);
  if (items == NULL)
    {
      PyErr_NoMemory ();
      return -1;
    }
  table->items = items;
  table->items[table->len].name = g_strdup (name);
  if (table->items[table->len].name == NULL)
    {
      PyErr_NoMemory ();
      return -1;
    }
  Py_INCREF (value);
  table->items[table->len].value = value;
  table->len++;
  return 0;
}

static int
object_table_remove_item (GinextObjectMetaTable *table, const char *name)
{
  for (Py_ssize_t i = 0; i < table->len; i++)
    {
      if (strcmp (table->items[i].name, name) != 0)
        continue;
      g_free (table->items[i].name);
      Py_DECREF (table->items[i].value);
      if (i != table->len - 1)
        table->items[i] = table->items[table->len - 1];
      table->len--;
      if (table->len == 0)
        {
          g_free (table->items);
          table->items = NULL;
        }
      return 1;
    }
  return 0;
}

static int
object_table_update_from_mapping (GinextObjectMetaTable *table, PyObject *mapping)
{
  PyObject *items = PyMapping_Items (mapping);
  if (items == NULL)
    return -1;
  PyObject *fast = PySequence_Fast (items, "metadata mapping items must be iterable");
  Py_DECREF (items);
  if (fast == NULL)
    return -1;

  Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);
  for (Py_ssize_t i = 0; i < n; i++)
    {
      PyObject *pair = PySequence_Fast_GET_ITEM (fast, i);
      if (!PyTuple_Check (pair) || PyTuple_GET_SIZE (pair) != 2)
        {
          PyErr_SetString (PyExc_TypeError, "metadata mapping items must be pairs");
          Py_DECREF (fast);
          return -1;
        }
      PyObject *key = PyTuple_GET_ITEM (pair, 0);
      const char *name = PyUnicode_AsUTF8 (key);
      if (name == NULL)
        {
          Py_DECREF (fast);
          return -1;
        }
      if (object_table_set_item (table, name, PyTuple_GET_ITEM (pair, 1)) < 0)
        {
          Py_DECREF (fast);
          return -1;
        }
    }
  Py_DECREF (fast);
  return 0;
}

static int
object_table_set_from_mapping (GinextObjectMetaTable *table, PyObject *mapping)
{
  GinextObjectMetaTable replacement = { 0 };
  if (object_table_update_from_mapping (&replacement, mapping) < 0)
    {
      object_table_clear (&replacement);
      return -1;
    }
  object_table_clear (table);
  *table = replacement;
  return 0;
}

static PyObject *
object_table_snapshot (GinextObjectMetaTable *table)
{
  PyObject *dict = PyDict_New ();
  if (dict == NULL)
    return NULL;
  for (Py_ssize_t i = 0; i < table->len; i++)
    {
      if (PyDict_SetItemString (dict, table->items[i].name, table->items[i].value) < 0)
        {
          Py_DECREF (dict);
          return NULL;
        }
    }
  return dict;
}

static PyObject *
object_table_keys (GinextObjectMetaTable *table)
{
  PyObject *list = PyList_New (table->len);
  if (list == NULL)
    return NULL;
  for (Py_ssize_t i = 0; i < table->len; i++)
    {
      PyObject *name = PyUnicode_FromString (table->items[i].name);
      if (name == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, i, name);
    }
  return list;
}

static PyObject *
property_table_pspecs_snapshot (GRegisteredTypeMetaObject *self)
{
  PyObject *dict = PyDict_New ();
  if (dict == NULL)
    return NULL;
  for (Py_ssize_t i = 0; i < self->n_properties; i++)
    {
      PyObject *value = PyLong_FromVoidPtr (self->properties[i].pspec);
      if (value == NULL
          || PyDict_SetItemString (dict, self->properties[i].name, value) < 0)
        {
          Py_XDECREF (value);
          Py_DECREF (dict);
          return NULL;
        }
      Py_DECREF (value);
    }
  return dict;
}

static PyObject *
property_table_prop_ids_snapshot (GRegisteredTypeMetaObject *self)
{
  PyObject *dict = PyDict_New ();
  if (dict == NULL)
    return NULL;
  for (Py_ssize_t i = 0; i < self->n_properties; i++)
    {
      PyObject *value = PyLong_FromUnsignedLong (self->properties[i].prop_id);
      if (value == NULL
          || PyDict_SetItemString (dict, self->properties[i].name, value) < 0)
        {
          Py_XDECREF (value);
          Py_DECREF (dict);
          return NULL;
        }
      Py_DECREF (value);
    }
  return dict;
}

/* ── from_type_name classmethod ──────────────────────────────────────────── */

static PyObject *
gimeta_from_type_name (PyTypeObject *cls G_GNUC_UNUSED, PyObject *args)
{
  const char *name;
  PyObject *gi_info = Py_None;
  if (!PyArg_ParseTuple (args, "s|O", &name, &gi_info))
    return NULL;

  GType gtype = g_type_from_name (name);
  Py_AUTO_DECREF PyObject *type_name = PyUnicode_FromString (name);
  Py_AUTO_DECREF PyObject *pspecs = PyDict_New ();
  Py_AUTO_DECREF PyObject *prop_ids = PyDict_New ();
  if (!type_name || !pspecs || !prop_ids)
    return NULL;

  PyObject *gm = gimeta_new (gtype, type_name, Py_None, pspecs, prop_ids, gi_info);
  if (gm)
    {
      /* gimeta_new steals references on success; defuse the auto-decrefs. */
      type_name = NULL;
      pspecs = NULL;
      prop_ids = NULL;
    }
  return gm;
}

static PyObject *
gimeta_from_gtype (PyTypeObject *cls G_GNUC_UNUSED, PyObject *args)
{
  unsigned long long gtype_arg = 0;
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "K|z", &gtype_arg, &name))
    return NULL;

  GType gtype = (GType)gtype_arg;
  if (name == NULL)
    name = g_type_name (gtype);
  if (name == NULL)
    name = "";

  Py_AUTO_DECREF PyObject *type_name = PyUnicode_FromString (name);
  Py_AUTO_DECREF PyObject *pspecs = PyDict_New ();
  Py_AUTO_DECREF PyObject *prop_ids = PyDict_New ();
  if (!type_name || !pspecs || !prop_ids)
    return NULL;

  PyObject *gm = gimeta_new (gtype, type_name, Py_None, pspecs, prop_ids, Py_None);
  if (gm)
    {
      type_name = NULL;
      pspecs = NULL;
      prop_ids = NULL;
    }
  return gm;
}

static PyObject *
gimeta_info_by_gtype (PyTypeObject *cls G_GNUC_UNUSED, PyObject *args)
{
  unsigned long long gtype_arg = 0;
  if (!PyArg_ParseTuple (args, "K", &gtype_arg))
    return NULL;
  return pygi_object_info_by_gtype ((GType)gtype_arg);
}

PyObject *
py_register_gobject_subclass (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *py_cls = NULL;
  PyObject *annotations = NULL;
  PyObject *requested_name_obj = NULL;
  if (!PyArg_ParseTuple (args,
                         "OO!U:register_gobject_subclass",
                         &py_cls,
                         &PyDict_Type,
                         &annotations,
                         &requested_name_obj))
    return NULL;
  const char *requested_name = PyUnicode_AsUTF8 (requested_name_obj);
  if (!requested_name)
    return NULL;
  return pygi_register_gobject_subclass_for_class (py_cls, annotations, requested_name);
}

static PyObject *
gimeta_list_property_names (GIMetaObject *self, PyObject *Py_UNUSED (ignored))
{
  if (self->gtype == G_TYPE_INVALID || !G_TYPE_IS_OBJECT (self->gtype))
    return PyList_New (0);

  gpointer klass = g_type_class_ref (self->gtype);
  if (klass == NULL)
    return PyList_New (0);

  guint n_props = 0;
  GParamSpec **props = g_object_class_list_properties (G_OBJECT_CLASS (klass), &n_props);
  PyObject *result = PyList_New ((Py_ssize_t)n_props);
  if (result == NULL)
    {
      g_free (props);
      g_type_class_unref (klass);
      return NULL;
    }
  for (guint i = 0; i < n_props; i++)
    {
      PyObject *name = PyUnicode_FromString (g_param_spec_get_name (props[i]));
      if (name == NULL)
        {
          Py_DECREF (result);
          g_free (props);
          g_type_class_unref (klass);
          return NULL;
        }
      PyList_SET_ITEM (result, (Py_ssize_t)i, name);
    }
  g_free (props);
  g_type_class_unref (klass);
  return result;
}

static PyObject *
gimeta_param_spec (GIMetaObject *self, PyObject *args)
{
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "s:param_spec", &name))
    return NULL;

  if (self->gtype == G_TYPE_INVALID || !G_TYPE_IS_OBJECT (self->gtype))
    Py_RETURN_NONE;

  gpointer klass = g_type_class_ref (self->gtype);
  if (klass == NULL)
    Py_RETURN_NONE;

  GParamSpec *pspec = g_object_class_find_property (G_OBJECT_CLASS (klass), name);
  PyObject *out = pygi_param_spec_new (pspec);
  g_type_class_unref (klass);
  return out;
}

static PyObject *
gimeta_install_native_vfunc_attrs (GIMetaObject *self G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  PyObject *gi_info = NULL;
  if (!PyArg_ParseTuple (args, "OO:install_native_vfunc_attrs", &cls, &gi_info))
    return NULL;
  if (pygi_install_native_vfunc_attrs_for_class (cls, gi_info) < 0)
    return NULL;
  Py_RETURN_NONE;
}

PyObject *
py_register_signal (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  unsigned long long gtype_arg = 0;
  const char *signal_name = NULL;
  unsigned long long return_gtype_arg = 0;
  PyObject *arg_gtypes_tuple = NULL;
  unsigned long long signal_flags_arg = G_SIGNAL_RUN_LAST;
  PyObject *accumulator_obj = Py_None;
  PyObject *accu_data_obj = Py_None;
  if (!PyArg_ParseTuple (args,
                         "KsKO!|KOO:register_signal",
                         &gtype_arg,
                         &signal_name,
                         &return_gtype_arg,
                         &PyTuple_Type,
                         &arg_gtypes_tuple,
                         &signal_flags_arg,
                         &accumulator_obj,
                         &accu_data_obj))
    return NULL;

  guint signal_id = 0;
  if (pygi_register_signal_for_gtype ((GType)gtype_arg,
                                      signal_name,
                                      (GType)return_gtype_arg,
                                      arg_gtypes_tuple,
                                      (GSignalFlags)signal_flags_arg,
                                      accumulator_obj,
                                      accu_data_obj,
                                      &signal_id)
      < 0)
    return NULL;
  return PyLong_FromUnsignedLong (signal_id);
}

static PyObject *
descriptor_lookup (GinextObjectMetaTable *table, const char *name, PyObject *default_value)
{
  GinextObjectMeta *item = object_table_lookup (table, name);
  if (item == NULL)
    return Py_NewRef (default_value);
  return Py_NewRef (item->value);
}

static PyObject *
gimeta_lookup_method (GIMetaObject *self, PyObject *args)
{
  const char *name = NULL;
  PyObject *default_value = Py_None;
  if (!PyArg_ParseTuple (args, "s|O:lookup_method", &name, &default_value))
    return NULL;
  return descriptor_lookup (&registered_meta (self)->method_infos, name, default_value);
}

static PyObject *
gimeta_list_methods (GIMetaObject *self, PyObject *Py_UNUSED (ignored))
{
  return object_table_keys (&registered_meta (self)->method_infos);
}

static PyObject *
gimeta_remove_method (GIMetaObject *self, PyObject *args)
{
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "s:remove_method", &name))
    return NULL;
  return PyBool_FromLong (object_table_remove_item (&registered_meta (self)->method_infos, name));
}

static PyObject *
gimeta_lookup_signal (GIMetaObject *self, PyObject *args)
{
  const char *name = NULL;
  PyObject *default_value = Py_None;
  if (!PyArg_ParseTuple (args, "s|O:lookup_signal", &name, &default_value))
    return NULL;
  return descriptor_lookup (&registered_meta (self)->signal_infos, name, default_value);
}

static PyObject *
gimeta_list_signals (GIMetaObject *self, PyObject *Py_UNUSED (ignored))
{
  return object_table_keys (&registered_meta (self)->signal_infos);
}

static PyObject *
gimeta_lookup_signal_method (GIMetaObject *self, PyObject *args)
{
  const char *name = NULL;
  PyObject *default_value = Py_None;
  if (!PyArg_ParseTuple (args, "s|O:lookup_signal_method", &name, &default_value))
    return NULL;
  return descriptor_lookup (&registered_meta (self)->signal_method_backings, name, default_value);
}

static PyObject *
gimeta_lookup_vfunc (GIMetaObject *self, PyObject *args)
{
  const char *name = NULL;
  PyObject *default_value = Py_None;
  if (!PyArg_ParseTuple (args, "s|O:lookup_vfunc", &name, &default_value))
    return NULL;
  return descriptor_lookup (&registered_meta (self)->vfunc_infos, name, default_value);
}

static PyObject *
gimeta_install_descriptors (GIMetaObject *self, PyObject *args)
{
  PyObject *method_infos = NULL;
  PyObject *signal_infos = NULL;
  PyObject *signal_method_backings = NULL;
  PyObject *vfunc_infos = NULL;
  if (!PyArg_ParseTuple (args,
                         "OOOO:install_descriptors",
                         &method_infos,
                         &signal_infos,
                         &signal_method_backings,
                         &vfunc_infos))
    return NULL;
  GRegisteredTypeMetaObject *registered = registered_meta (self);
  if (object_table_update_from_mapping (&registered->method_infos, method_infos) < 0
      || object_table_update_from_mapping (&registered->signal_infos, signal_infos) < 0
      || object_table_update_from_mapping (&registered->signal_method_backings, signal_method_backings) < 0
      || object_table_update_from_mapping (&registered->vfunc_infos, vfunc_infos) < 0)
    return NULL;
  Py_RETURN_NONE;
}

static PyObject *
gimeta_inherit_descriptors_from (GIMetaObject *self, PyObject *arg)
{
  if (!PyObject_TypeCheck (arg, &GIMetaType))
    {
      PyErr_SetString (PyExc_TypeError, "inherit_descriptors_from expects a GIMeta");
      return NULL;
    }
  GRegisteredTypeMetaObject *registered = registered_meta (self);
  GRegisteredTypeMetaObject *parent = registered_meta ((GIMetaObject *)arg);
  for (Py_ssize_t i = 0; i < parent->signal_infos.len; i++)
    {
      GinextObjectMeta *item = &parent->signal_infos.items[i];
      if (object_table_set_item (&registered->signal_infos, item->name, item->value) < 0)
        return NULL;
    }
  for (Py_ssize_t i = 0; i < parent->signal_method_backings.len; i++)
    {
      GinextObjectMeta *item = &parent->signal_method_backings.items[i];
      if (object_table_set_item (&registered->signal_method_backings, item->name, item->value) < 0)
        return NULL;
    }
  for (Py_ssize_t i = 0; i < parent->vfunc_infos.len; i++)
    {
      GinextObjectMeta *item = &parent->vfunc_infos.items[i];
      if (object_table_set_item (&registered->vfunc_infos, item->name, item->value) < 0)
        return NULL;
    }
  Py_RETURN_NONE;
}

/* ── property access: walk MRO, find owning gimeta, hit InstancePrivate ─── */

/* Look up (pspec, prop_id) for `name` on one GIMeta. Returns 1 on success,
 * 0 when not found on this meta, and -1 with an exception. */
static int
resolve_pspec_in_gimeta (GIMetaObject *m,
                         const char *name,
                         GParamSpec **out_pspec,
                         guint *out_prop_id)
{
  GinextPropertyMeta *property = property_table_lookup (registered_meta (m), name);
  if (property == NULL)
    return 0;
  *out_pspec = property->pspec;
  *out_prop_id = property->prop_id;
  return 1;
}

static int
resolve_pspec (PyObject *obj, const char *name, GParamSpec **out_pspec, guint *out_prop_id)
{
  PyTypeObject *type = Py_TYPE (obj);
  PyObject *mro = type->tp_mro; /* borrowed; owned by type */
  if (!mro)
    {
      PyErr_SetString (PyExc_RuntimeError, "type has no __mro__");
      return -1;
    }
  Py_ssize_t n = PyTuple_GET_SIZE (mro);
  for (Py_ssize_t i = 0; i < n; i++)
    {
      PyObject *cls = PyTuple_GET_ITEM (mro, i); /* borrowed */
      Py_AUTO_DECREF PyObject *gimeta = NULL;
      if (PyObject_GetOptionalAttrString (cls, "gimeta", &gimeta) < 0)
        return -1;
      if (!gimeta || !PyObject_TypeCheck (gimeta, &GIMetaType))
        continue;
      int resolved = resolve_pspec_in_gimeta ((GIMetaObject *)gimeta, name, out_pspec, out_prop_id);
      if (resolved < 0)
        return -1;
      if (resolved > 0)
        return 0;
    }
  PyErr_Format (PyExc_AttributeError, "%s has no property %s", type->tp_name, name);
  return -1;
}

/* Extract the underlying GObject* from a Python ginext wrapper. */
static GObject *
gobject_from_py (PyObject *py_obj)
{
  GObject *obj = pygi_gobject_get (py_obj);
  if (!obj)
    return NULL;
  if (!obj && !PyErr_Occurred ())
    PyErr_SetString (PyExc_ValueError, "GObject pointer is NULL");
  return obj;
}

static PyObject *
gimeta_get_property (GIMetaObject *self G_GNUC_UNUSED, PyObject *args)
{
  PyObject *py_obj;
  const char *name;
  if (!PyArg_ParseTuple (args, "Os", &py_obj, &name))
    return NULL;

  GObject *g_obj = gobject_from_py (py_obj);
  if (!g_obj)
    return NULL;

  GParamSpec *pspec;
  guint prop_id;
  int resolved = resolve_pspec_in_gimeta (self, name, &pspec, &prop_id);
  if (resolved < 0)
    return NULL;
  if (resolved == 0 && resolve_pspec (py_obj, name, &pspec, &prop_id) < 0)
    return NULL;

  if (!(pspec->flags & G_PARAM_READABLE))
    {
      PyErr_Format (PyExc_AttributeError,
                    "property %s on %s is not readable",
                    name,
                    Py_TYPE (py_obj)->tp_name);
      return NULL;
    }

  /* Bypass g_object_get_property: walk straight to the GValue slot.
     * Tradeoffs documented in object_property.c-equivalent comments. */
  InstancePrivate *priv = instance_private_from_type ((GTypeInstance *)g_obj, pspec->owner_type);
  return pygi_gvalue_value_to_py (&priv->props[prop_id - 1]);
}

PyObject *
py_gobject_get_property (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  GIMetaObject *gimeta = NULL;
  PyObject *py_obj = NULL;
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "O!Os:gobject_get_property", &GIMetaType, &gimeta, &py_obj, &name))
    return NULL;
  PyObject *method_args = Py_BuildValue ("Os", py_obj, name);
  if (method_args == NULL)
    return NULL;
  PyObject *result = gimeta_get_property (gimeta, method_args);
  Py_DECREF (method_args);
  return result;
}

static PyObject *
gimeta_set_property (GIMetaObject *self G_GNUC_UNUSED, PyObject *args)
{
  PyObject *py_obj;
  const char *name;
  PyObject *value;
  if (!PyArg_ParseTuple (args, "OsO", &py_obj, &name, &value))
    return NULL;

  GObject *g_obj = gobject_from_py (py_obj);
  if (!g_obj)
    return NULL;

  GParamSpec *pspec;
  guint prop_id;
  int resolved = resolve_pspec_in_gimeta (self, name, &pspec, &prop_id);
  if (resolved < 0)
    return NULL;
  if (resolved == 0 && resolve_pspec (py_obj, name, &pspec, &prop_id) < 0)
    return NULL;

  if (!(pspec->flags & G_PARAM_WRITABLE))
    {
      PyErr_Format (PyExc_AttributeError,
                    "property %s on %s is read-only",
                    name,
                    Py_TYPE (py_obj)->tp_name);
      return NULL;
    }
  if (pspec->flags & G_PARAM_CONSTRUCT_ONLY)
    {
      PyErr_Format (PyExc_AttributeError,
                    "property %s on %s is construct-only",
                    name,
                    Py_TYPE (py_obj)->tp_name);
      return NULL;
    }

  InstancePrivate *priv = instance_private_from_type ((GTypeInstance *)g_obj, pspec->owner_type);
  if (pygi_py_to_gvalue_property (value, &priv->props[prop_id - 1]) < 0)
    return NULL;
  /* Emit notify::<name> so signal handlers attached via
     * `obj.notify[name].connect(...)` fire as a side effect of the
     * assignment. The direct fast-path write bypasses
     * g_object_set_property (and the notify it would emit), so we
     * trigger the equivalent emission explicitly. */
  g_object_notify_by_pspec (g_obj, pspec);
  Py_RETURN_NONE;
}

PyObject *
py_gobject_set_property (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  GIMetaObject *gimeta = NULL;
  PyObject *py_obj = NULL;
  const char *name = NULL;
  PyObject *value = NULL;
  if (!PyArg_ParseTuple (args,
                         "O!OsO:gobject_set_property",
                         &GIMetaType,
                         &gimeta,
                         &py_obj,
                         &name,
                         &value))
    return NULL;
  PyObject *method_args = Py_BuildValue ("OsO", py_obj, name, value);
  if (method_args == NULL)
    return NULL;
  PyObject *result = gimeta_set_property (gimeta, method_args);
  Py_DECREF (method_args);
  return result;
}

/* ── type machinery: dealloc, getsets, methods, type slots ───────────────── */

static void
gimeta_dealloc (GIMetaObject *self)
{
  GRegisteredTypeMetaObject *registered = registered_meta (self);
  Py_XDECREF (self->type_name);
  Py_XDECREF (self->gi_info);
  Py_XDECREF (self->namespace);
  Py_XDECREF (self->profile);
  Py_XDECREF (registered->parent);
  property_table_clear (registered);
  Py_XDECREF (registered->method_owner_name);
  object_table_clear (&registered->method_infos);
  Py_XDECREF (registered->typelib_methods);
  object_table_clear (&registered->signal_infos);
  object_table_clear (&registered->signal_method_backings);
  object_table_clear (&registered->vfunc_infos);
  Py_XDECREF (registered->extensions);
  Py_TYPE (self)->tp_free ((PyObject *)self);
}

static PyObject *
gimeta_repr (GIMetaObject *self)
{
  return PyUnicode_FromFormat ("<GIMeta type_name=%R gtype=%llu n_pspecs=%zd>",
                               self->type_name,
                               (unsigned long long)self->gtype,
                               registered_meta (self)->n_properties);
}

static PyObject *
gimeta_get_gtype (GIMetaObject *self, void *closure G_GNUC_UNUSED)
{
  return PyLong_FromUnsignedLongLong (self->gtype);
}

#define GETSET_OBJ(field)                                                                          \
  static PyObject *gimeta_get_##field (GIMetaObject *self, void *closure G_GNUC_UNUSED)            \
  {                                                                                                \
    Py_INCREF (self->field);                                                                       \
    return self->field;                                                                            \
  }
GETSET_OBJ (type_name)
GETSET_OBJ (gi_info)
GETSET_OBJ (namespace)
GETSET_OBJ (profile)
#undef GETSET_OBJ

#define GETSET_REG_OBJ(field)                                                                      \
  static PyObject *gimeta_get_##field (GIMetaObject *self, void *closure G_GNUC_UNUSED)            \
  {                                                                                                \
    PyObject *value = registered_meta (self)->field;                                               \
    Py_INCREF (value);                                                                             \
    return value;                                                                                  \
  }
GETSET_REG_OBJ (parent)
GETSET_REG_OBJ (method_owner_name)
#undef GETSET_REG_OBJ

static PyObject *
gimeta_get_extensions (GIMetaObject *self, void *closure G_GNUC_UNUSED)
{
  GRegisteredTypeMetaObject *registered = registered_meta (self);
  if (registered->extensions == NULL)
    {
      registered->extensions = PyDict_New ();
      if (registered->extensions == NULL)
        return NULL;
    }
  return Py_NewRef (registered->extensions);
}

static PyObject *
gimeta_get_typelib_methods (GIMetaObject *self, void *closure G_GNUC_UNUSED)
{
  GRegisteredTypeMetaObject *registered = registered_meta (self);
  if (registered->typelib_methods == NULL)
    {
      registered->typelib_methods = PyDict_New ();
      if (registered->typelib_methods == NULL)
        return NULL;
    }
  return Py_NewRef (registered->typelib_methods);
}

#define GETSET_TABLE(field)                                                                        \
  static PyObject *gimeta_get_##field (GIMetaObject *self, void *closure G_GNUC_UNUSED)            \
  {                                                                                                \
    return object_table_snapshot (&registered_meta (self)->field);                                 \
  }
GETSET_TABLE (method_infos)
GETSET_TABLE (signal_infos)
GETSET_TABLE (signal_method_backings)
GETSET_TABLE (vfunc_infos)
#undef GETSET_TABLE

static PyObject *
gimeta_get_pspecs (GIMetaObject *self, void *closure G_GNUC_UNUSED)
{
  return property_table_pspecs_snapshot (registered_meta (self));
}

static PyObject *
gimeta_get_prop_ids (GIMetaObject *self, void *closure G_GNUC_UNUSED)
{
  return property_table_prop_ids_snapshot (registered_meta (self));
}

#define SETSET_OBJ(field)                                                                          \
  static int gimeta_set_##field (GIMetaObject *self, PyObject *value, void *closure G_GNUC_UNUSED) \
  {                                                                                                \
    if (!value)                                                                                    \
      {                                                                                            \
        PyErr_SetString (PyExc_TypeError, #field " cannot be deleted");                            \
        return -1;                                                                                 \
      }                                                                                            \
    Py_INCREF (value);                                                                             \
    Py_SETREF (self->field, value);                                                                \
    return 0;                                                                                      \
  }
SETSET_OBJ (namespace)
SETSET_OBJ (profile)
#undef SETSET_OBJ

#define SETSET_REG_OBJ(field)                                                                      \
  static int gimeta_set_##field (GIMetaObject *self, PyObject *value, void *closure G_GNUC_UNUSED) \
  {                                                                                                \
    if (!value)                                                                                    \
      {                                                                                            \
        PyErr_SetString (PyExc_TypeError, #field " cannot be deleted");                            \
        return -1;                                                                                 \
      }                                                                                            \
    Py_INCREF (value);                                                                             \
    Py_SETREF (registered_meta (self)->field, value);                                              \
    return 0;                                                                                      \
  }
SETSET_REG_OBJ (method_owner_name)
SETSET_REG_OBJ (typelib_methods)
SETSET_REG_OBJ (extensions)
#undef SETSET_REG_OBJ

#define SETSET_TABLE(field)                                                                        \
  static int gimeta_set_##field (GIMetaObject *self, PyObject *value, void *closure G_GNUC_UNUSED) \
  {                                                                                                \
    if (!value)                                                                                    \
      {                                                                                            \
        PyErr_SetString (PyExc_TypeError, #field " cannot be deleted");                            \
        return -1;                                                                                 \
      }                                                                                            \
    return object_table_set_from_mapping (&registered_meta (self)->field, value);                  \
  }
SETSET_TABLE (method_infos)
SETSET_TABLE (signal_infos)
SETSET_TABLE (signal_method_backings)
SETSET_TABLE (vfunc_infos)
#undef SETSET_TABLE

static PyGetSetDef gimeta_getsets[]
    = { { "gtype", (getter)gimeta_get_gtype, NULL, "GType identifier", NULL },
        { "type_name", (getter)gimeta_get_type_name, NULL, "Registered GType name", NULL },
        { "parent", (getter)gimeta_get_parent, NULL, "Parent Python class", NULL },
        { "pspecs", (getter)gimeta_get_pspecs, NULL, "{name: pspec_ptr_as_int}", NULL },
        { "prop_ids", (getter)gimeta_get_prop_ids, NULL, "{name: 1-based prop_id}", NULL },
        { "gi_info", (getter)gimeta_get_gi_info, NULL, "GIBaseInfo capsule", NULL },
        { "namespace",
          (getter)gimeta_get_namespace,
          (setter)gimeta_set_namespace,
          "Namespace object",
          NULL },
        { "method_owner_name",
          (getter)gimeta_get_method_owner_name,
          (setter)gimeta_set_method_owner_name,
          "Qualified owner name for imported methods",
          NULL },
        { "method_infos",
          (getter)gimeta_get_method_infos,
          (setter)gimeta_set_method_infos,
          "{name: (GIBaseInfo, has_self)} for imported methods",
          NULL },
        { "typelib_methods",
          (getter)gimeta_get_typelib_methods,
          (setter)gimeta_set_typelib_methods,
          "{name: callable} for saved typelib methods",
          NULL },
        { "signal_infos",
          (getter)gimeta_get_signal_infos,
          (setter)gimeta_set_signal_infos,
          "{name: signal_info_or_descriptor}",
          NULL },
        { "signal_method_backings",
          (getter)gimeta_get_signal_method_backings,
          (setter)gimeta_set_signal_method_backings,
          "{name: callable} for method/signal collision resolution",
          NULL },
        { "vfunc_infos",
          (getter)gimeta_get_vfunc_infos,
          (setter)gimeta_set_vfunc_infos,
          "{name: vfunc_info}",
          NULL },
        { "profile",
          (getter)gimeta_get_profile,
          (setter)gimeta_set_profile,
          "ABI profile for this wrapper",
          NULL },
        { "extensions",
          (getter)gimeta_get_extensions,
          (setter)gimeta_set_extensions,
          "Toolkit-specific authoring metadata",
          NULL },
        { 0 } };

static PyMethodDef gimeta_methods[]
    = { { "from_type_name",
          (PyCFunction)gimeta_from_type_name,
          METH_VARARGS | METH_CLASS,
          "Build a GIMeta for an already-registered GType, by name." },
        { "info_by_gtype",
          (PyCFunction)gimeta_info_by_gtype,
          METH_VARARGS | METH_CLASS,
          "Resolve GI object or interface info by GType." },
        { "from_gtype",
          (PyCFunction)gimeta_from_gtype,
          METH_VARARGS | METH_CLASS,
          "Build a GIMeta from a raw GType and optional type name." },
        { "param_spec",
          (PyCFunction)gimeta_param_spec,
          METH_VARARGS,
          "Resolve a ParamSpec by canonical GObject property name." },
        { "list_property_names",
          (PyCFunction)gimeta_list_property_names,
          METH_NOARGS,
          "List GObject property names for this GType." },
        { "lookup_method", (PyCFunction)gimeta_lookup_method, METH_VARARGS, NULL },
        { "list_methods", (PyCFunction)gimeta_list_methods, METH_NOARGS, NULL },
        { "remove_method", (PyCFunction)gimeta_remove_method, METH_VARARGS, NULL },
        { "lookup_signal", (PyCFunction)gimeta_lookup_signal, METH_VARARGS, NULL },
        { "list_signals", (PyCFunction)gimeta_list_signals, METH_NOARGS, NULL },
        { "lookup_signal_method", (PyCFunction)gimeta_lookup_signal_method, METH_VARARGS, NULL },
        { "lookup_vfunc", (PyCFunction)gimeta_lookup_vfunc, METH_VARARGS, NULL },
        { "install_descriptors", (PyCFunction)gimeta_install_descriptors, METH_VARARGS, NULL },
        { "inherit_descriptors_from", (PyCFunction)gimeta_inherit_descriptors_from, METH_O, NULL },
        { "install_native_vfunc_attrs",
          (PyCFunction)gimeta_install_native_vfunc_attrs,
          METH_VARARGS,
          "Install native vfunc chain-up wrappers on a class." },
        { NULL } };

PyTypeObject GIMetaType = {
  PyVarObject_HEAD_INIT (NULL, 0).tp_name = "ginext.private._gobject.GIMeta",
  .tp_basicsize = sizeof (GRegisteredTypeMetaObject),
  .tp_dealloc = (destructor)gimeta_dealloc,
  .tp_repr = (reprfunc)gimeta_repr,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = "Per-class registration record for ginext GObject subclasses.",
  .tp_methods = gimeta_methods,
  .tp_getset = gimeta_getsets,
};

PyObject *
gimeta_new (GType gtype,
            PyObject *type_name,
            PyObject *parent,
            PyObject *pspecs,
            PyObject *prop_ids,
            PyObject *gi_info)
{
  GRegisteredTypeMetaObject *registered
      = PyObject_New (GRegisteredTypeMetaObject, &GIMetaType);
  if (!registered)
    return NULL;
  registered->base.gtype = G_TYPE_INVALID;
  registered->base.type_name = NULL;
  registered->base.gi_info = NULL;
  registered->base.namespace = NULL;
  registered->base.profile = NULL;
  registered->parent = NULL;
  registered->properties = NULL;
  registered->n_properties = 0;
  registered->method_owner_name = NULL;
  registered->method_infos = (GinextObjectMetaTable){ 0 };
  registered->typelib_methods = NULL;
  registered->signal_infos = (GinextObjectMetaTable){ 0 };
  registered->signal_method_backings = (GinextObjectMetaTable){ 0 };
  registered->vfunc_infos = (GinextObjectMetaTable){ 0 };
  registered->extensions = NULL;
  GIMetaObject *self = &registered->base;
  self->kind = GINEXT_META_REGISTERED_TYPE;
  self->gtype = gtype;
  self->type_name = Py_NewRef (type_name);
  self->gi_info = Py_NewRef (gi_info);
  self->namespace = Py_NewRef (Py_None);
  self->profile = Py_NewRef (Py_None);
  registered->parent = Py_NewRef (parent);
  if (property_table_set_from_dicts (registered, pspecs, prop_ids) < 0)
    {
      Py_DECREF (self);
      return NULL;
    }
  registered->method_owner_name = Py_NewRef (Py_None);
  return (PyObject *)self;
}
