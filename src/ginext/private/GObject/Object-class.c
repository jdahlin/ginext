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

/* GLib-side ClassData lifecycle and the four GObject vfuncs ginext installs
 * on every subclass: set_property/get_property (called by GLib's
 * g_object_*_property dispatch), instance_init (per-instance GValue store
 * initialization), and class_init (one-time install of the pspecs).
 *
 * These never call into Python — they're driven by GLib during
 * g_object_new and friends. The Python-facing dispatch in
 * object_get_property.c bypasses these entirely for speed; they remain
 * here as the fallback path g_object_set_property still goes through.
 */
#include "common.h"
#include "GObject/Object-info.h"
#include "GObject/Object.h"

static void
maybe_run_python_instance_init (GTypeInstance *instance, gpointer klass)
{
  GObject *object = G_OBJECT (instance);
  if (object == NULL || !G_IS_OBJECT (object))
    return;

  PyGILState_STATE gil = PyGILState_Ensure ();

  int is_active = pygi_python_construction_active ();
  if (is_active < 0)
    {
      PyErr_WriteUnraisable (Py_None);
      PyGILState_Release (gil);
      return;
    }
  if (is_active > 0)
    {
      PyGILState_Release (gil);
      return;
    }

  Py_AUTO_DECREF PyObject *existing_wrapper = pygi_gobject_wrapper_ref (object);
  if (existing_wrapper != NULL)
    {
      PyGILState_Release (gil);
      return;
    }
  if (PyErr_Occurred ())
    {
      PyErr_WriteUnraisable (Py_None);
      PyGILState_Release (gil);
      return;
    }

  GType wrapper_gtype = G_TYPE_FROM_CLASS (klass);
  Py_AUTO_DECREF PyObject *wrapper = pygi_wrap_preallocated_gobject (object, wrapper_gtype);
  if (wrapper == NULL)
    {
      PyErr_WriteUnraisable (Py_None);
      PyGILState_Release (gil);
      return;
    }
  if (wrapper == Py_None)
    {
      PyGILState_Release (gil);
      return;
    }

  if (!PyObject_TypeCheck (wrapper, pygi_gobject_type)
      || ((PyGIGObject *)wrapper)->construction_ptr == NULL)
    {
      PyGILState_Release (gil);
      return;
    }

  if (pygi_gobject_wrapper_pin (object, wrapper) < 0)
    {
      PyErr_WriteUnraisable (wrapper);
      PyGILState_Release (gil);
      return;
    }

  Py_AUTO_DECREF PyObject *init
      = PyObject_GetAttrString ((PyObject *)Py_TYPE (wrapper), "__init__");
  if (init == NULL)
    {
      pygi_gobject_wrapper_unpin (object);
      PyErr_WriteUnraisable (wrapper);
      PyGILState_Release (gil);
      return;
    }

  Py_AUTO_DECREF PyObject *initialized = PyObject_CallFunctionObjArgs (init, wrapper, NULL);
  if (initialized == NULL)
    {
      pygi_gobject_wrapper_clear (object);
      pygi_gobject_wrapper_forget_pointer (wrapper);
      pygi_gobject_wrapper_unpin (object);
      PyErr_WriteUnraisable (wrapper);
      PyGILState_Release (gil);
      return;
    }

  PyGILState_Release (gil);
}

static GQuark
class_state_quark (void)
{
  static gsize quark_value = 0;
  if (g_once_init_enter (&quark_value))
    {
      GQuark quark = g_quark_from_static_string ("ginext-class-state");
      g_once_init_leave (&quark_value, (gsize)quark);
    }
  return (GQuark)quark_value;
}

void
class_data_free (gpointer p)
{
  ClassData *data = p;
  for (guint i = 0; i < data->n_props; i++)
    g_param_spec_unref (data->pspecs[i]);
  g_free (data->pspecs);
  g_free (data);
}

static ClassState *
class_state_from_class (gpointer klass, size_t offset)
{
  return (ClassState *)((guint8 *)klass + offset);
}

ClassState *
class_state_from_type (GType gtype)
{
  return g_type_get_qdata (gtype, class_state_quark ());
}

InstancePrivate *
instance_private_from_type (GTypeInstance *instance, GType gtype)
{
  ClassState *state = class_state_from_type (gtype);
  return (InstancePrivate *)G_STRUCT_MEMBER_P (instance, state->private_offset);
}

/* GObject vfuncs. Reached by g_object_set_property/g_object_get_property
 * when something other than ginext's fast path triggers the dispatch
 * (e.g. a future signal that emits a property change). */
static void
set_property (GObject *obj, guint prop_id, const GValue *value, GParamSpec *pspec)
{
  ClassState *owner_state = class_state_from_type (pspec->owner_type);
  ClassData *owner_data = owner_state ? owner_state->data : NULL;
  if (owner_state != NULL && owner_data != NULL && prop_id >= 1 && prop_id <= owner_data->n_props)
    {
      InstancePrivate *priv = instance_private_from_type ((GTypeInstance *)obj, pspec->owner_type);
      g_value_copy (value, &priv->props[prop_id - 1]);
      return;
    }

  ClassState *state = class_state_from_type (G_OBJECT_TYPE (obj));
  if (state != NULL && state->parent_set_property != NULL)
    {
      state->parent_set_property (obj, prop_id, value, pspec);
      return;
    }

  G_OBJECT_WARN_INVALID_PROPERTY_ID (obj, prop_id, pspec);
}

static void
get_property (GObject *obj, guint prop_id, GValue *value, GParamSpec *pspec)
{
  ClassState *owner_state = class_state_from_type (pspec->owner_type);
  ClassData *owner_data = owner_state ? owner_state->data : NULL;
  if (owner_state != NULL && owner_data != NULL && prop_id >= 1 && prop_id <= owner_data->n_props)
    {
      InstancePrivate *priv = instance_private_from_type ((GTypeInstance *)obj, pspec->owner_type);
      g_value_copy (&priv->props[prop_id - 1], value);
      return;
    }

  ClassState *state = class_state_from_type (G_OBJECT_TYPE (obj));
  if (state != NULL && state->parent_get_property != NULL)
    {
      state->parent_get_property (obj, prop_id, value, pspec);
      return;
    }

  G_OBJECT_WARN_INVALID_PROPERTY_ID (obj, prop_id, pspec);
}

void
ginext_instance_init (GTypeInstance *instance, gpointer klass)
{
  /* This hook is called by GLib from any thread (e.g. from GStreamer's
   * streaming thread during element creation inside gst_parse_launch).
   * Acquire the GIL here since we touch Python-managed ClassState/ClassData
   * structures and eventually call maybe_run_python_instance_init. */
  PyGILState_STATE gil = PyGILState_Ensure ();

  /* GLib runs instance_init once per class in the inheritance chain —
     * parent first, then child. The `klass` argument is always the leaf,
     * so we walk the chain ourselves and init each level idempotently:
     * the `g_type != 0` check on the first prop short-circuits levels
     * already initialized by an earlier slot's invocation. */
  for (GType cur = G_TYPE_FROM_INSTANCE (instance); cur && cur != G_TYPE_OBJECT;
       cur = g_type_parent (cur))
    {
      ClassState *state = class_state_from_type (cur);
      ClassData *data = state ? state->data : NULL;
      if (!data || data->n_props == 0)
        continue;

      InstancePrivate *priv = instance_private_from_type (instance, cur);
      if (priv->props[0].g_type != 0)
        continue;

      for (guint i = 0; i < data->n_props; i++)
        {
          g_value_init (&priv->props[i], data->pspecs[i]->value_type);
          g_param_value_set_default (data->pspecs[i], &priv->props[i]);
        }
    }

  maybe_run_python_instance_init (instance, klass);
  PyGILState_Release (gil);
}

void
ginext_class_init (gpointer klass, gpointer user_data)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);
  GObjectClass *parent_class = g_type_class_peek_parent (klass);
  GType gtype = G_TYPE_FROM_CLASS (klass);
  ClassData *data = user_data;
  ClassState *state = class_state_from_class (klass, data->class_state_offset);

  state->data = data;
  state->gtype = gtype;
  state->parent_set_property = parent_class ? parent_class->set_property : NULL;
  state->parent_get_property = parent_class ? parent_class->get_property : NULL;
  g_type_set_qdata (gtype, class_state_quark (), state);
  gobject_class->set_property = set_property;
  gobject_class->get_property = get_property;

  /* g_type_add_instance_private asserts size > 0, so skip the call
     * entirely when there's nothing to allocate. The returned offset is
     * raw and needs g_type_class_adjust_private_offset to account for
     * parent instance sizes — without that, the offset lands inside the
     * GObject struct and clobbers ref_count/qdata. */
  if (data->n_props > 0)
    {
      state->private_offset = g_type_add_instance_private (gtype,
                                                           sizeof (InstancePrivate)
                                                               + data->n_props * sizeof (GValue));
      g_type_class_adjust_private_offset (klass, &state->private_offset);
    }
  else
    {
      state->private_offset = 0;
    }

  for (guint i = 0; i < data->n_props; i++)
    g_object_class_install_property (gobject_class, i + 1, data->pspecs[i]);
}
