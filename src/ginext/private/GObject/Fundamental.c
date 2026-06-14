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
#include "hooks.h"
#include "marshal/conversion.h"
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


static GIFieldInfo *
fundamental_lookup_field (GIObjectInfo *info, const char *name)
{
  GIObjectInfo *cur = (GIObjectInfo *)gi_base_info_ref ((GIBaseInfo *)info);
  while (cur != NULL)
    {
      unsigned int n = gi_object_info_get_n_fields (cur);
      for (unsigned int fi = 0; fi < n; fi++)
        {
          GIFieldInfo *field = gi_object_info_get_field (cur, fi);
          if (field == NULL)
            continue;
          const char *candidate = gi_base_info_get_name ((GIBaseInfo *)field);
          if (candidate != NULL && strcmp (candidate, name) == 0)
            {
              gi_base_info_unref ((GIBaseInfo *)cur);
              return field;
            }
          gi_base_info_unref ((GIBaseInfo *)field);
        }
      GIObjectInfo *parent = gi_object_info_get_parent (cur);
      gi_base_info_unref ((GIBaseInfo *)cur);
      cur = parent;
    }
  return NULL;
}

static PyObject *
fundamental_get_field (PyGIFundamental *self, const char *name)
{
  g_autoptr (GIObjectInfo) info = object_info_for_gtype (self->gtype);
  if (info == NULL)
    return NULL;

  GIFieldInfo *field = fundamental_lookup_field (info, name);
  if (field == NULL)
    return NULL;

  if (!(gi_field_info_get_flags (field) & GI_FIELD_IS_READABLE))
    {
      gi_base_info_unref ((GIBaseInfo *)field);
      return NULL;
    }

  g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
  size_t offset = (size_t)gi_field_info_get_offset (field);
  gi_base_info_unref ((GIBaseInfo *)field);

  PyGIType type;
  if (pygi_type_from_gi (fti, &type) != 0)
    return NULL;
  PyGIValue val = pygi_value_for_memory (&type, (char *)self->instance + offset);
  return pygi_value_to_py (&val);
}

static void
Fundamental_dealloc (PyObject *self)
{
  PyGIFundamental *f = (PyGIFundamental *)self;
  gpointer instance = f->instance;
  GType gtype = f->gtype;
  f->instance = NULL;
  f->gtype = 0;
  PyTypeObject *tp = Py_TYPE (self);
  if (tp->tp_weaklistoffset)
    PyObject_ClearWeakRefs (self);
  tp->tp_free (self);
  if (instance != NULL)
    pygi_instantiatable_unref (instance, gtype);
  Py_DECREF (tp);
}

static PyObject *
Fundamental_repr (PyObject *self)
{
  PyGIFundamental *f = (PyGIFundamental *)self;
  const char *type_name = g_type_name (f->gtype);
  if (type_name == NULL)
    type_name = Py_TYPE (self)->tp_name;
  return PyUnicode_FromFormat ("<%s at 0x%zx>", type_name,
                               (Py_ssize_t)(uintptr_t)f->instance);
}

static PyObject *
Fundamental_richcompare (PyObject *self, PyObject *other, int op)
{
  if (op != Py_EQ && op != Py_NE)
    Py_RETURN_NOTIMPLEMENTED;
  if (!pygi_fundamental_check (other))
    Py_RETURN_NOTIMPLEMENTED;
  int eq = ((PyGIFundamental *)self)->instance == ((PyGIFundamental *)other)->instance;
  return PyBool_FromLong (op == Py_EQ ? eq : !eq);
}

static Py_hash_t
Fundamental_hash (PyObject *self)
{
  return (Py_hash_t)(uintptr_t)((PyGIFundamental *)self)->instance;
}

static PyObject *
Fundamental_getattro (PyObject *self, PyObject *name)
{
  PyObject *res = PyObject_GenericGetAttr (self, name);
  if (res != NULL || !PyErr_ExceptionMatches (PyExc_AttributeError))
    return res;
  PyErr_Clear ();

  const char *name_str = PyUnicode_AsUTF8 (name);
  if (name_str == NULL)
    return NULL;
  if (name_str[0] != '_')
    {
      PyGIFundamental *f = (PyGIFundamental *)self;
      if (f->instance != NULL)
        {
          PyObject *field_val = fundamental_get_field (f, name_str);
          if (field_val != NULL)
            return field_val;
          if (PyErr_Occurred ())
            return NULL;
        }
    }

  if (pygi_hook_method_for_instance != NULL)
    {
      PyObject *call_args = PyTuple_Pack (2, self, name);
      if (call_args == NULL)
        return NULL;
      PyObject *method = pygi_hook_call_first (pygi_hook_method_for_instance, call_args);
      Py_DECREF (call_args);
      if (method == NULL)
        {
          if (!PyErr_ExceptionMatches (PyExc_AttributeError))
            return NULL;
          PyErr_Clear ();
        }
      else
        {
          if (method != Py_None)
            return method;
          Py_DECREF (method);
        }
    }

  PyErr_SetObject (PyExc_AttributeError, name);
  return NULL;
}

static PyObject *
Fundamental_new (PyTypeObject *type, PyObject *args G_GNUC_UNUSED, PyObject *kwargs G_GNUC_UNUSED)
{
  PyErr_Format (PyExc_TypeError,
                "%s cannot be instantiated directly; use the type's factory method",
                type->tp_name);
  return NULL;
}

static PyMemberDef Fundamental_members[] = {
  { "__instance_ptr__", Py_T_ULONGLONG, offsetof (PyGIFundamental, instance), Py_READONLY, NULL },
  { "__gtype__", Py_T_ULONGLONG, offsetof (PyGIFundamental, gtype), Py_READONLY, NULL },
  { NULL }
};

static PyType_Slot Fundamental_slots[] = {
  { Py_tp_new, Fundamental_new },
  { Py_tp_dealloc, Fundamental_dealloc },
  { Py_tp_repr, Fundamental_repr },
  { Py_tp_richcompare, Fundamental_richcompare },
  { Py_tp_hash, Fundamental_hash },
  { Py_tp_getattro, Fundamental_getattro },
  { Py_tp_members, Fundamental_members },
  { 0, NULL },
};

static PyType_Spec Fundamental_spec = {
  .name = "ginext._gobject.Fundamental",
  .basicsize = sizeof (PyGIFundamental),
  .itemsize = 0,
  .flags = (Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_HEAPTYPE),
  .slots = Fundamental_slots,
};

PyTypeObject *PyGIFundamental_Type = NULL;

int
pygi_fundamental_type_init (void)
{
  PyObject *type = PyType_FromSpec (&Fundamental_spec);
  if (type == NULL)
    return -1;
  PyGIFundamental_Type = (PyTypeObject *)type;
  return 0;
}


PyObject *
pygi_fundamental_new (PyTypeObject *type, gpointer instance, GType gtype)
{
  PyGIFundamental *self = (PyGIFundamental *)type->tp_alloc (type, 0);
  if (self == NULL)
    return NULL;
  self->instance = instance;
  self->gtype = gtype;
  return (PyObject *)self;
}


PyObject *
pygi_fundamental_to_py (gpointer instance, GITransfer transfer, PyObject *wrapper_type)
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
  if (wrapper_type == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "GObject wrapper type is not registered");
      pygi_instantiatable_unref (instance, actual_gtype);
      return NULL;
    }
  if (!PyType_Check (wrapper_type) || !PyType_IsSubtype ((PyTypeObject *)wrapper_type, PyGIFundamental_Type))
    {
      PyErr_SetString (PyExc_TypeError, "expected Fundamental subclass for fundamental wrapper");
      pygi_instantiatable_unref (instance, actual_gtype);
      return NULL;
    }
  return pygi_fundamental_new ((PyTypeObject *)wrapper_type, instance, actual_gtype);
}
