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

#include "GObject/Fundamental.h"

#include "common.h"
#include "marshal/enum.h"

typedef struct
{
  PyGIRefFunc ref_func;
  PyGIUnrefFunc unref_func;
} LifecycleFuncs;

static GHashTable *lifecycle_table = NULL;

void
pygi_register_lifecycle_funcs (GType gtype, PyGIRefFunc ref_func, PyGIUnrefFunc unref_func)
{
  if (lifecycle_table == NULL)
    lifecycle_table = g_hash_table_new_full (NULL, NULL, NULL, g_free);

  LifecycleFuncs *funcs = g_new (LifecycleFuncs, 1);
  funcs->ref_func = ref_func;
  funcs->unref_func = unref_func;
  g_hash_table_insert (lifecycle_table, GSIZE_TO_POINTER (gtype), funcs);
}

static GIObjectInfo *
object_info_for_gtype (GType gtype)
{
  GIRepository *repository = ginext_shared_repository ();
  GIBaseInfo *info = gi_repository_find_by_gtype (repository, gtype);
  if (info != NULL && GI_IS_OBJECT_INFO (info))
    return (GIObjectInfo *)info;
  if (info != NULL)
    gi_base_info_unref (info);

  GType fundamental = G_TYPE_FUNDAMENTAL (gtype);
  if (fundamental == 0 || fundamental == gtype)
    return NULL;
  info = gi_repository_find_by_gtype (repository, fundamental);
  if (info != NULL && GI_IS_OBJECT_INFO (info))
    return (GIObjectInfo *)info;
  if (info != NULL)
    gi_base_info_unref (info);
  return NULL;
}

typedef gpointer (*LifecycleFuncGetter) (GIObjectInfo *info);

static gpointer
ref_func_for_info (GIObjectInfo *info)
{
  return gi_object_info_get_ref_function_pointer (info);
}

static gpointer
unref_func_for_info (GIObjectInfo *info)
{
  return gi_object_info_get_unref_function_pointer (info);
}

static GIObjectInfo *
object_info_for_lifecycle_func (GType actual_gtype,
                                GType declared_gtype,
                                LifecycleFuncGetter getter,
                                gpointer *out_func)
{
  GIObjectInfo *info = object_info_for_gtype (actual_gtype);
  gpointer func = info != NULL ? getter (info) : NULL;
  if (func != NULL)
    {
      *out_func = func;
      return info;
    }
  if (info != NULL)
    gi_base_info_unref ((GIBaseInfo *)info);

  if (declared_gtype != G_TYPE_INVALID && declared_gtype != G_TYPE_NONE
      && declared_gtype != actual_gtype)
    {
      info = object_info_for_gtype (declared_gtype);
      func = info != NULL ? getter (info) : NULL;
      if (func != NULL)
        {
          *out_func = func;
          return info;
        }
      if (info != NULL)
        gi_base_info_unref ((GIBaseInfo *)info);
    }

  GType fundamental = G_TYPE_FUNDAMENTAL (actual_gtype);
  if (fundamental == G_TYPE_INVALID || fundamental == actual_gtype || fundamental == declared_gtype)
    return NULL;

  info = object_info_for_gtype (fundamental);
  func = info != NULL ? getter (info) : NULL;
  if (func != NULL)
    {
      *out_func = func;
      return info;
    }
  if (info != NULL)
    gi_base_info_unref ((GIBaseInfo *)info);
  return NULL;
}

int
pygi_instantiatable_ref (gpointer instance, GType gtype, gpointer *out_instance)
{
  if (out_instance == NULL)
    {
      PyErr_SetString (PyExc_SystemError, "pygi_instantiatable_ref: NULL out pointer");
      return -1;
    }
  *out_instance = NULL;
  if (instance == NULL)
    return 0;

  if (G_IS_OBJECT (instance))
    {
      *out_instance = g_object_ref (instance);
      return 0;
    }

  GType actual_gtype = G_TYPE_FROM_INSTANCE ((GTypeInstance *)instance);
  if (gtype == G_TYPE_INVALID || gtype == G_TYPE_NONE)
    gtype = actual_gtype;

  if (lifecycle_table != NULL)
    {
      LifecycleFuncs *funcs
          = g_hash_table_lookup (lifecycle_table, GSIZE_TO_POINTER (actual_gtype));
      if (funcs == NULL)
        {
          GType base = G_TYPE_FUNDAMENTAL (actual_gtype);
          if (base != actual_gtype)
            funcs = g_hash_table_lookup (lifecycle_table, GSIZE_TO_POINTER (base));
        }
      if (funcs != NULL && funcs->ref_func != NULL)
        {
          *out_instance = funcs->ref_func (instance);
          return 0;
        }
    }

  gpointer ref_func_ptr = NULL;
  g_autoptr (GIObjectInfo) info
      = object_info_for_lifecycle_func (actual_gtype, gtype, ref_func_for_info, &ref_func_ptr);
  if (info == NULL)
    {
      PyErr_Format (PyExc_TypeError,
                    "no introspection object info for instantiatable type %s",
                    g_type_name (actual_gtype));
      return -1;
    }
  GIObjectInfoRefFunction ref_func = (GIObjectInfoRefFunction)ref_func_ptr;
  *out_instance = ref_func (instance);
  return 0;
}

int
pygi_instantiatable_unref (gpointer instance, GType gtype)
{
  if (instance == NULL)
    return 0;

  if (G_IS_OBJECT (instance))
    {
      g_object_unref (instance);
      return 0;
    }

  GType actual_gtype = G_TYPE_FROM_INSTANCE ((GTypeInstance *)instance);
  if (gtype == G_TYPE_INVALID || gtype == G_TYPE_NONE)
    gtype = actual_gtype;

  if (lifecycle_table != NULL)
    {
      LifecycleFuncs *funcs
          = g_hash_table_lookup (lifecycle_table, GSIZE_TO_POINTER (actual_gtype));
      if (funcs == NULL)
        {
          GType base = G_TYPE_FUNDAMENTAL (actual_gtype);
          if (base != actual_gtype)
            funcs = g_hash_table_lookup (lifecycle_table, GSIZE_TO_POINTER (base));
        }
      if (funcs != NULL && funcs->unref_func != NULL)
        {
          funcs->unref_func (instance);
          return 0;
        }
    }

  gpointer unref_func_ptr = NULL;
  g_autoptr (GIObjectInfo) info
      = object_info_for_lifecycle_func (actual_gtype, gtype, unref_func_for_info, &unref_func_ptr);
  if (info == NULL)
    {
      PyErr_Format (PyExc_TypeError,
                    "no introspection object info for instantiatable type %s",
                    g_type_name (actual_gtype));
      return -1;
    }
  GIObjectInfoUnrefFunction unref_func = (GIObjectInfoUnrefFunction)unref_func_ptr;
  unref_func (instance);
  return 0;
}

PyObject *
pygi_fundamental_to_py (gpointer instance, GITransfer transfer, PyObject *wrapper_factory)
{
  if (instance == NULL)
    return Py_NewRef (Py_None);

  GType actual_gtype = G_TYPE_FROM_INSTANCE ((GTypeInstance *)instance);
  if (!G_TYPE_IS_INSTANTIATABLE (actual_gtype))
    {
      PyErr_SetString (PyExc_NotImplementedError,
                       "TODO ginext: non-GObject pointer returns are outside the current slice");
      return NULL;
    }
  if (transfer == GI_TRANSFER_NOTHING)
    {
      gpointer owned = NULL;
      if (pygi_instantiatable_ref (instance, actual_gtype, &owned) != 0)
        return NULL;
      instance = owned;
    }
  if (wrapper_factory == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "GObject wrapper factory is not registered");
      pygi_instantiatable_unref (instance, actual_gtype);
      return NULL;
    }

  PyObject *ptr = PyLong_FromVoidPtr (instance);
  if (ptr == NULL)
    {
      pygi_instantiatable_unref (instance, actual_gtype);
      return NULL;
    }
  PyObject *actual = PyLong_FromUnsignedLongLong ((unsigned long long)actual_gtype);
  if (actual == NULL)
    {
      Py_DECREF (ptr);
      pygi_instantiatable_unref (instance, actual_gtype);
      return NULL;
    }
  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    {
      Py_DECREF (actual);
      Py_DECREF (ptr);
      pygi_instantiatable_unref (instance, actual_gtype);
      return NULL;
    }
  PyObject *wrapper = PyObject_CallFunctionObjArgs (wrapper_factory, ptr, actual, context, NULL);
  Py_DECREF (actual);
  Py_DECREF (ptr);
  if (wrapper == NULL)
    pygi_instantiatable_unref (instance, actual_gtype);
  return wrapper;
}

PyObject *
py_instantiatable_unref (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  gpointer instance = PyLong_AsVoidPtr (ptr_obj);
  if (PyErr_Occurred ())
    return NULL;
  if (pygi_instantiatable_unref (instance, G_TYPE_INVALID) != 0)
    return NULL;
  Py_RETURN_NONE;
}
