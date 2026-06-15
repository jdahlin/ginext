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

#include "GObject/hooks.h"
#include "GLib/Array.h"
#include "GLib/HashTable.h"
#include "GLib/List.h"
#include "GObject/Boxed.h"
#include "GObject/GIMeta.h"
#include "GObject/Object.h"
#include "GObject/Object-info.h"
#include "GIRepository/BaseInfo.h"
#include "GIRepository/Info.h"
#include "marshal/conversion.h"
#include "marshal/container-element.h"
#include "marshal/enum.h"
#include "marshal/marshal.h"
#include "marshal/gvalue.h"
#include "GObject/Value.h"
#include "marshal/scalar.h"
#include "marshal/string.h"
#include "runtime/type-info.h"
#include "runtime/module_funcs.h"
#include "runtime/class-registry.h"
#include "gimeta-helpers.h"
#include "GObject/field-descr.h"

#include <girepository/girepository.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define info_from_capsule gi_info_from_py

static PyObject *boxed_classes_by_gtype = NULL;

static PyObject *
profile_name_from_object (PyObject *obj)
{
  PyObject *profile = PyObject_GetAttrString (obj, "_profile");
  if (profile == NULL)
    {
      PyErr_Clear ();
      PyObject *type = (PyObject *)Py_TYPE (obj);
      PyObject *gimeta = NULL;
      if (pygi_object_get_gimeta (type, &gimeta) < 0)
        {
          PyErr_Clear ();
          gimeta = NULL;
        }
      if (gimeta == NULL)
        {
          PyErr_Clear ();
          if (pygi_object_get_gimeta (obj, &gimeta) < 0)
            {
              PyErr_Clear ();
              gimeta = NULL;
            }
        }
      if (gimeta != NULL)
        {
          if (pygi_gimeta_get_profile (gimeta, &profile) < 0)
            {
              PyErr_Clear ();
              profile = NULL;
            }
          Py_DECREF (gimeta);
        }
      if (profile == NULL)
        PyErr_Clear ();
    }
  if (profile == NULL)
    return PyUnicode_FromString ("native");
  PyObject *name = PyObject_GetAttrString (profile, "name");
  Py_DECREF (profile);
  if (name == NULL)
    {
      PyErr_Clear ();
      return PyUnicode_FromString ("native");
    }
  return name;
}

static PyObject *
profile_name_from_context (void)
{
  PyObject *context = pygi_namespace_context ();
  if (context == NULL)
    return NULL;
  return profile_name_from_object (context);
}

static PyObject *
boxed_registry_key (GType gtype, PyObject *profile_name)
{
  PyObject *gtype_obj = PyLong_FromUnsignedLongLong ((unsigned long long)gtype);
  if (gtype_obj == NULL)
    return NULL;
  PyObject *key = PyTuple_Pack (2, profile_name, gtype_obj);
  Py_DECREF (gtype_obj);
  return key;
}

PyObject *
pygi_class_registry_get_pytype_for_gtype (GType gtype)
{
  if (boxed_classes_by_gtype == NULL || gtype == 0)
    return NULL;
  PyObject *profile_name = profile_name_from_context ();
  if (profile_name == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  PyObject *key = boxed_registry_key (gtype, profile_name);
  Py_DECREF (profile_name);
  if (key == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  PyObject *cls = PyDict_GetItemWithError (boxed_classes_by_gtype, key);
  Py_DECREF (key);
  if (cls == NULL && PyErr_Occurred ())
    PyErr_Clear ();
  return cls;
}

typedef struct
{
  GSource source;
  PyObject *py_wrapper;
} PyGIEventSource;

PyObject *
pygi_error_to_py (GIArgument *arg, GITransfer transfer)
{
  GError *err = (GError *)arg->v_pointer;
  if (err == NULL)
    return Py_XNewRef (Py_None);

  PyObject *factory = pygi_hook_last (pygi_hook_exception_from_gerror);
  PyObject *result = NULL;
  if (factory != NULL)
    {
      result = PyObject_CallFunction (factory,
                                      "kis",
                                      (unsigned long)err->domain,
                                      err->code,
                                      err->message ? err->message : "");
    }
  if (result != NULL)
    {
      if (transfer != GI_TRANSFER_NOTHING)
        g_error_free (err);
      return result;
    }
  PyErr_Clear ();

  PyObject *tuple = PyTuple_New (3);
  if (tuple == NULL)
    return NULL;
  PyTuple_SET_ITEM (tuple, 0, PyUnicode_FromString (g_quark_to_string (err->domain)));
  PyTuple_SET_ITEM (tuple, 1, PyLong_FromLong (err->code));
  PyTuple_SET_ITEM (tuple, 2, PyUnicode_FromString (err->message ? err->message : ""));
  if (transfer != GI_TRANSFER_NOTHING)
    g_error_free (err);
  return tuple;
}

static int
pygi_error_fields_from_tuple (PyObject *obj,
                              PyObject **domain_out,
                              PyObject **code_out,
                              PyObject **message_out)
{
  if (!PyTuple_Check (obj) || PyTuple_GET_SIZE (obj) != 3)
    return 0;

  *domain_out = Py_NewRef (PyTuple_GET_ITEM (obj, 0));
  *code_out = Py_NewRef (PyTuple_GET_ITEM (obj, 1));
  *message_out = Py_NewRef (PyTuple_GET_ITEM (obj, 2));
  return 1;
}

static int
pygi_error_fields_from_attrs (PyObject *obj,
                              PyObject **domain_out,
                              PyObject **code_out,
                              PyObject **message_out)
{
  PyObject *domain = PyObject_GetAttrString (obj, "domain");
  if (domain == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }

  PyObject *code = PyObject_GetAttrString (obj, "code");
  if (code == NULL)
    {
      Py_DECREF (domain);
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }

  PyObject *message = PyObject_GetAttrString (obj, "message");
  if (message == NULL)
    {
      Py_DECREF (domain);
      Py_DECREF (code);
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }

  *domain_out = domain;
  *code_out = code;
  *message_out = message;
  return 1;
}

int
pygi_error_from_py (PyObject *obj, GError **out_error)
{
  g_return_val_if_fail (out_error != NULL, -1);
  *out_error = NULL;

  if (obj == Py_None)
    return 1;

  PyObject *domain_obj = NULL;
  PyObject *code_obj = NULL;
  PyObject *message_obj = NULL;
  int rc = pygi_error_fields_from_tuple (obj, &domain_obj, &code_obj, &message_obj);
  if (rc == 0)
    rc = pygi_error_fields_from_attrs (obj, &domain_obj, &code_obj, &message_obj);
  if (rc <= 0)
    return rc;

  GQuark domain = 0;
  if (PyUnicode_Check (domain_obj))
    {
      const char *domain_str = PyUnicode_AsUTF8 (domain_obj);
      if (domain_str == NULL)
        {
          rc = -1;
          goto out;
        }
      domain = g_quark_from_string (domain_str);
    }
  else if (PyLong_Check (domain_obj))
    {
      unsigned long value = PyLong_AsUnsignedLong (domain_obj);
      if (value == (unsigned long)-1 && PyErr_Occurred ())
        {
          rc = -1;
          goto out;
        }
      domain = (GQuark)value;
    }
  else
    {
      PyErr_Format (PyExc_TypeError,
                    "GLib.Error domain must be str or int, not %.200s",
                    Py_TYPE (domain_obj)->tp_name);
      rc = -1;
      goto out;
    }

  long code = PyLong_AsLong (code_obj);
  if (code == -1 && PyErr_Occurred ())
    {
      rc = -1;
      goto out;
    }

  if (!PyUnicode_Check (message_obj))
    {
      PyErr_Format (PyExc_TypeError,
                    "GLib.Error message must be str, not %.200s",
                    Py_TYPE (message_obj)->tp_name);
      rc = -1;
      goto out;
    }
  const char *message = PyUnicode_AsUTF8 (message_obj);
  if (message == NULL)
    {
      rc = -1;
      goto out;
    }

  *out_error = g_error_new_literal (domain, (gint)code, message);
  rc = *out_error != NULL ? 1 : -1;

out:
  Py_XDECREF (domain_obj);
  Py_XDECREF (code_obj);
  Py_XDECREF (message_obj);
  return rc;
}

int
pygi_boxed_check (PyObject *obj)
{
  return obj != NULL && obj != Py_None && pygi_gboxed_base_type != NULL
         && PyObject_TypeCheck (obj, pygi_gboxed_base_type);
}

int
pygi_boxed_get (PyObject *obj, gpointer *out)
{
  if (obj == NULL || obj == Py_None)
    {
      if (out != NULL)
        *out = NULL;
      return 0;
    }
  if (!pygi_boxed_check (obj))
    {
      PyErr_Format (PyExc_TypeError,
                    "expected a GLib.Boxed wrapper, got %.200s",
                    Py_TYPE (obj)->tp_name);
      return -1;
    }
  if (out != NULL)
    *out = ((PyGIGLibBoxed *)obj)->boxed;
  return 0;
}

PyObject *
pygi_boxed_new (PyObject *cls, gpointer boxed, GType gtype, int transfer_full)
{
  if (cls == NULL || !PyType_Check (cls))
    {
      PyErr_SetString (PyExc_SystemError, "GLib.Boxed: cls is not a type");
      return NULL;
    }
  PyObject *self = ((PyTypeObject *)cls)->tp_alloc ((PyTypeObject *)cls, 0);
  if (self == NULL)
    return NULL;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  me->boxed = boxed;
  me->gtype = gtype;
  me->borrowed = transfer_full ? 0 : 1;
  me->heap_allocated = 0;
  me->size = 0;
  me->py_dict = NULL;
  me->parent = NULL;
  return self;
}

PyObject *
pygi_boxed_new_alias (PyObject *cls, gpointer boxed, GType gtype, PyObject *parent)
{
  PyObject *self = pygi_boxed_new (cls, boxed, gtype, 0);
  if (self == NULL)
    return NULL;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  me->borrowed = 1;
  me->parent = parent;
  Py_XINCREF (parent);
  return self;
}

int
pygi_boxed_promote_borrowed_alias (PyObject *obj)
{
  if (obj == NULL || !pygi_boxed_check (obj))
    return 0;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)obj;
  /* Only borrowed aliases into transient memory need promoting; an alias kept
   * alive by a parent already has a stable backing object. */
  if (!me->borrowed || me->parent != NULL || me->boxed == NULL)
    return 0;
  if (me->gtype == 0 || !G_TYPE_IS_BOXED (me->gtype))
    return 0;
  gpointer copy = g_boxed_copy (me->gtype, me->boxed);
  if (copy == NULL)
    return 0;
  me->boxed = copy;
  me->borrowed = 0;
  return 1;
}

PyObject *
pygi_boxed_new_heap (PyObject *cls, gpointer boxed, GType gtype, gsize size)
{
  if (cls == NULL || !PyType_Check (cls))
    {
      PyErr_SetString (PyExc_SystemError, "GLib.Boxed: cls is not a type");
      return NULL;
    }
  PyObject *self = ((PyTypeObject *)cls)->tp_alloc ((PyTypeObject *)cls, 0);
  if (self == NULL)
    return NULL;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  me->boxed = boxed;
  me->gtype = gtype;
  me->borrowed = 0;
  me->heap_allocated = 1;
  me->size = size;
  me->py_dict = NULL;
  me->parent = NULL;
  return self;
}

#define PYGI_RECORD_CLASS_DATA_CAPSULE "_ginext_record_class_data"

typedef struct
{
  GIBaseInfo *info;
  GType gtype;
  gsize size;
} PyGIRecordClassData;

static void
record_class_data_destroy (PyObject *capsule)
{
  PyGIRecordClassData *data
      = PyCapsule_GetPointer (capsule, PYGI_RECORD_CLASS_DATA_CAPSULE);
  if (data == NULL)
    return;
  if (data->info != NULL)
    gi_base_info_unref (data->info);
  g_free (data);
}

static PyGIRecordClassData *
record_class_data_for_type (PyTypeObject *type)
{
  PyObject *capsule = NULL;
  if (PyObject_GetOptionalAttrString ((PyObject *)type, "__record_data__", &capsule) < 0)
    return NULL;
  if (capsule == NULL)
    return NULL;
  PyGIRecordClassData *data
      = PyCapsule_GetPointer (capsule, PYGI_RECORD_CLASS_DATA_CAPSULE);
  Py_DECREF (capsule);
  return data;
}

static PyObject *
GBoxedBase_new (PyTypeObject *type, PyObject *args, PyObject *kwds)
{
  if ((args != NULL && PyTuple_GET_SIZE (args) != 0)
      || (kwds != NULL && PyDict_GET_SIZE (kwds) != 0))
    {
      PyErr_SetString (PyExc_TypeError, "GLib.Boxed construction does not accept arguments");
      return NULL;
    }

  PyGIRecordClassData *data = record_class_data_for_type (type);
  if (data == NULL)
    {
      if (!PyErr_Occurred ())
        PyErr_SetString (PyExc_TypeError, "direct GLib.Boxed construction is unsupported");
      return NULL;
    }

  gsize size = data->size != 0 ? data->size : sizeof (void *);
  gpointer boxed = g_malloc0 (size);
  if (boxed == NULL)
    return PyErr_NoMemory ();
  PyObject *self = pygi_boxed_new_heap ((PyObject *)type, boxed, data->gtype, size);
  if (self == NULL)
    {
      g_free (boxed);
      return NULL;
    }
  return self;
}

static void
GBoxedBase_dealloc (PyObject *self)
{
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  gpointer boxed = me->boxed;
  GType gtype = me->gtype;
  int borrowed = me->borrowed;
  int heap_allocated = me->heap_allocated;
  gsize size = me->size;
  PyObject *py_dict = me->py_dict;
  PyObject *parent = me->parent;

  me->boxed = NULL;
  me->gtype = 0;
  me->borrowed = 0;
  me->heap_allocated = 0;
  me->size = 0;
  me->py_dict = NULL;
  me->parent = NULL;

  if (boxed != NULL && !borrowed)
    {
      if (heap_allocated)
        {
          if (gtype == G_TYPE_VALUE && ((GValue *)boxed)->g_type != 0)
            g_value_unset ((GValue *)boxed);
          g_free (boxed);
        }
      else if (gtype == G_TYPE_VARIANT)
        g_variant_unref ((GVariant *)boxed);
      else if (gtype != 0)
        g_boxed_free (gtype, boxed);
      else if (size != 0)
        g_free (boxed);
    }
  Py_XDECREF (py_dict);
  Py_XDECREF (parent);
  Py_TYPE (self)->tp_free (self);
}

static PyObject *
GBoxedBase_repr (PyObject *self)
{
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  PyTypeObject *type = Py_TYPE (self);
  PyObject *module = NULL;
  PyObject *stripped = NULL;
  PyObject *name = NULL;
  PyObject *qualified = NULL;
  PyObject *result = NULL;

  module = PyType_GetModuleName (type);
  if (module == NULL || !PyUnicode_Check (module))
    {
      PyErr_Clear ();
      Py_XDECREF (module);
      module = PyUnicode_FromString ("");
      if (module == NULL)
        return NULL;
    }
  stripped = pygi_strip_known_module_prefixes (module);
  if (stripped == NULL)
    goto done;
  name = PyType_GetName (type);
  if (name == NULL)
    goto done;
  if (PyUnicode_GET_LENGTH (stripped) > 0)
    qualified = PyUnicode_FromFormat ("%U.%U", stripped, name);
  else
    qualified = Py_NewRef (name);
  if (qualified == NULL)
    goto done;

  if (me->boxed == NULL)
    result = PyUnicode_FromFormat ("<%U object at %p (%s detached)>",
                                   qualified,
                                   (void *)self,
                                   me->gtype != 0 ? g_type_name (me->gtype) : "?");
  else
    result = PyUnicode_FromFormat ("<%U object at %p (%s at %p)>",
                                   qualified,
                                   (void *)self,
                                   me->gtype != 0 ? g_type_name (me->gtype) : "?",
                                   me->boxed);

done:
  Py_XDECREF (module);
  Py_XDECREF (stripped);
  Py_XDECREF (name);
  Py_XDECREF (qualified);
  return result;
}

static PyObject *
GBoxedBase_copy (PyObject *self, PyObject *Py_UNUSED (ignored))
{
  gpointer ptr = NULL;
  if (pygi_boxed_get (self, &ptr) != 0)
    return NULL;
  if (ptr == NULL)
    Py_RETURN_NONE;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)self;
  if (me->gtype == 0)
    {
      PyErr_SetString (PyExc_TypeError, "record has no boxed GType");
      return NULL;
    }
  gpointer copy = g_boxed_copy (me->gtype, ptr);
  if (copy == NULL)
    Py_RETURN_NONE;
  return pygi_boxed_new ((PyObject *)Py_TYPE (self), copy, me->gtype, 1);
}

static PyObject *
GBoxedBase_richcompare (PyObject *self, PyObject *other, int op)
{
  if (op != Py_EQ && op != Py_NE)
    Py_RETURN_NOTIMPLEMENTED;
  if (Py_TYPE (self) != Py_TYPE (other))
    Py_RETURN_NOTIMPLEMENTED;
  gpointer left_ptr = NULL;
  gpointer right_ptr = NULL;
  if (pygi_boxed_get (self, &left_ptr) != 0)
    return NULL;
  if (pygi_boxed_get (other, &right_ptr) != 0)
    return NULL;
  int equal = left_ptr == right_ptr;
  return PyBool_FromLong (op == Py_EQ ? equal : !equal);
}

static Py_hash_t
GBoxedBase_hash (PyObject *self)
{
  gpointer ptr = NULL;
  if (pygi_boxed_get (self, &ptr) != 0)
    return -1;
  Py_hash_t hash = (Py_hash_t)(uintptr_t)ptr;
  return hash == -1 ? -2 : hash;
}

static PyMethodDef GBoxedBase_methods[] = {
  { "copy", GBoxedBase_copy, METH_NOARGS, NULL },
  { NULL, NULL, 0, NULL },
};

static PyType_Slot PyGIGLibBoxed_slots[] = {
  { Py_tp_new, GBoxedBase_new },
  { Py_tp_dealloc, GBoxedBase_dealloc },
  { Py_tp_repr, GBoxedBase_repr },
  { Py_tp_methods, GBoxedBase_methods },
  { Py_tp_richcompare, GBoxedBase_richcompare },
  { Py_tp_hash, GBoxedBase_hash },
  { 0, NULL },
};

PyType_Spec PyGIGLibBoxed_spec = {
  .name = "GLib.Boxed",
  .basicsize = sizeof (PyGIGLibBoxed),
  .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .slots = PyGIGLibBoxed_slots,
};

static gsize
record_info_size (GIBaseInfo *info)
{
  if (GI_IS_STRUCT_INFO (info))
    return gi_struct_info_get_size ((GIStructInfo *)info);
  if (GI_IS_UNION_INFO (info))
    return gi_union_info_get_size ((GIUnionInfo *)info);
  return 0;
}

static int
record_lookup_field (GIBaseInfo *info, const char *field_name, GIFieldInfo **field_out)
{
  if (info == NULL || field_name == NULL)
    return 0;
  int n_fields = gi_struct_or_union_n_fields (info);
  for (int fi = 0; fi < n_fields; fi++)
    {
      GIFieldInfo *field = gi_struct_or_union_get_field (info, (guint)fi);
      if (field == NULL)
        continue;
      const char *candidate = gi_base_info_get_name ((GIBaseInfo *)field);
      if (candidate != NULL && strcmp (candidate, field_name) == 0)
        {
          if (field_out != NULL)
            *field_out = field;
          else
            gi_base_info_unref ((GIBaseInfo *)field);
          return 1;
        }
      gi_base_info_unref ((GIBaseInfo *)field);
    }
  return 0;
}

static PyObject *
record_build_class_for_info (GIBaseInfo *info, PyObject *context)
{
  if (info == NULL)
    Py_RETURN_NONE;
  const char *namespace_name = gi_base_info_get_namespace (info);
  const char *name = gi_base_info_get_name (info);
  if (namespace_name == NULL || name == NULL)
    Py_RETURN_NONE;

  PyObject *resolver = pygi_hook_last (pygi_hook_class_from_namespace_profile);
  if (resolver == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "class_from_namespace_profile hook not registered");
      return NULL;
    }
  PyObject *resolved_context = context != NULL ? context : pygi_namespace_context ();
  if (resolved_context == NULL)
    return NULL;
  return PyObject_CallFunction (resolver, "Oss", resolved_context, namespace_name, name);
}

static PyObject *
boxed_shadow_get (PyObject *parent, const char *name)
{
  if (!pygi_boxed_check (parent) || name == NULL)
    Py_RETURN_NONE;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)parent;
  if (me->py_dict == NULL)
    Py_RETURN_NONE;
  PyObject *value = PyDict_GetItemString (me->py_dict, name);
  if (value == NULL)
    Py_RETURN_NONE;
  return Py_NewRef (value);
}

static int
boxed_shadow_set (PyObject *parent, const char *name, PyObject *value)
{
  if (!pygi_boxed_check (parent) || name == NULL)
    return -1;
  PyGIGLibBoxed *me = (PyGIGLibBoxed *)parent;
  if (me->py_dict == NULL)
    {
      me->py_dict = PyDict_New ();
      if (me->py_dict == NULL)
        return -1;
    }
  return PyDict_SetItemString (me->py_dict, name, value);
}

PyObject *
union_interface_field_shadow_to_py (GITypeInfo *fti,
                                    char *base,
                                    size_t offset,
                                    PyObject *parent,
                                    const char *field_name)
{
  g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
  if (finfo == NULL || (!GI_IS_STRUCT_INFO (finfo) && !GI_IS_UNION_INFO (finfo)))
    return NULL;

  PyObject *cached = boxed_shadow_get (parent, field_name);
  if (cached == NULL)
    return NULL;
  if (cached != Py_None)
    return cached;
  Py_DECREF (cached);

  gsize size = record_info_size (finfo);
  if (size == 0)
    size = sizeof (void *);
  gpointer copy = g_malloc0 (size);
  if (copy == NULL)
    return PyErr_NoMemory ();
  memcpy (copy, base + offset, size);

  PyObject *cls = record_build_class_for_info (finfo, parent);
  if (cls == NULL)
    {
      g_free (copy);
      return NULL;
    }
  GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)finfo);
  PyObject *out = pygi_boxed_new_heap (cls, copy, gtype, size);
  Py_DECREF (cls);
  if (out == NULL)
    {
      g_free (copy);
      return NULL;
    }
  if (boxed_shadow_set (parent, field_name, out) != 0)
    {
      Py_DECREF (out);
      return NULL;
    }
  return out;
}

static PyObject *
array_field_to_py (GITypeInfo *fti, char *base, size_t offset, PyObject *parent)
{
  g_autoptr (GITypeInfo) inner_ti = gi_type_info_get_param_type (fti, 0);
  if (inner_ti == NULL)
    {
      PyErr_SetString (PyExc_NotImplementedError, "array field has no element type info");
      return NULL;
    }

  if (gi_type_info_get_array_type (fti) == GI_ARRAY_TYPE_ARRAY)
    {
      GArray *array = *(GArray **)((void *)(base + offset));
      if (array == NULL)
        Py_RETURN_NONE;

      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      if (itag == GI_TYPE_TAG_VOID || itag == GI_TYPE_TAG_UINT8)
        {
          PyObject *list = PyList_New ((Py_ssize_t)array->len);
          if (list == NULL)
            return NULL;
          for (guint i = 0; i < array->len; i++)
            {
              PyObject *item = PyLong_FromUnsignedLong ((guint8)array->data[i]);
              if (item == NULL)
                {
                  Py_DECREF (list);
                  return NULL;
                }
              PyList_SET_ITEM (list, (Py_ssize_t)i, item);
            }
          return list;
        }

      PyErr_SetString (PyExc_NotImplementedError, "unsupported GArray field element type");
      return NULL;
    }

  if (gi_type_info_get_array_type (fti) == GI_ARRAY_TYPE_PTR_ARRAY)
    {
      gpointer ptr = *(gpointer *)((void *)(base + offset));
      if (ptr == NULL)
        return PyList_New (0);
      GIArgument arg = { .v_pointer = ptr };
      return pygi_garray_to_py (NULL, fti, &arg, GI_TRANSFER_NOTHING);
    }

  if (gi_type_info_get_array_type (fti) != GI_ARRAY_TYPE_C)
    {
      PyErr_SetString (PyExc_NotImplementedError, "unsupported array field type");
      return NULL;
    }

  if (gi_type_info_is_zero_terminated (fti))
    {
      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      if (itag == GI_TYPE_TAG_UTF8 || itag == GI_TYPE_TAG_FILENAME)
        {
          gchar **strv = *(gchar ***)((void *)(base + offset));
          return pygi_strv_to_py_list (strv, GI_TRANSFER_NOTHING);
        }
      if (itag == GI_TYPE_TAG_INTERFACE)
        {
          g_autoptr (GIBaseInfo) iinfo = gi_type_info_get_interface (inner_ti);
          gpointer *arr = *(gpointer **)((void *)(base + offset));
          gsize len = 0;
          if (arr != NULL)
            while (arr[len] != NULL)
              len++;
          PyObject *list = PyList_New ((Py_ssize_t)len);
          if (list == NULL)
            return NULL;
          if (iinfo == NULL || (!GI_IS_STRUCT_INFO (iinfo) && !GI_IS_UNION_INFO (iinfo)))
            return list;
          GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iinfo);
          PyObject *cls = record_build_class_for_info (iinfo, parent);
          if (cls == NULL)
            {
              Py_DECREF (list);
              return NULL;
            }
          for (gsize i = 0; i < len; i++)
            {
              PyObject *item = pygi_boxed_new_alias (cls, arr[i], gtype, parent);
              if (item == NULL)
                {
                  Py_DECREF (cls);
                  Py_DECREF (list);
                  return NULL;
                }
              PyList_SET_ITEM (list, (Py_ssize_t)i, item);
            }
          Py_DECREF (cls);
          return list;
        }
    }

  size_t fixed = 0;
  if (gi_type_info_get_array_fixed_size (fti, &fixed) && fixed > 0)
    {
      PyGIContainerElement element;
      if (pygi_container_element_init (&element, inner_ti) != 0)
        return NULL;
      gsize elem_size = pygi_container_element_inline_size (&element);
      if (elem_size == 0)
        {
          PyErr_SetString (PyExc_NotImplementedError, "unsupported fixed-array element size");
          return NULL;
        }
      PyObject *list = PyList_New ((Py_ssize_t)fixed);
      if (list == NULL)
        return NULL;
      char *array = base + offset;
      for (size_t i = 0; i < fixed; i++)
        {
          PyObject *item
              = pygi_container_element_inline_to_py (&element, array + ((gsize)i * elem_size));
          if (item == NULL)
            {
              Py_DECREF (list);
              return NULL;
            }
          PyList_SET_ITEM (list, (Py_ssize_t)i, item);
        }
      return list;
    }
  PyErr_SetString (PyExc_NotImplementedError,
                   "array field shape (e.g. length-annotated C array) not implemented");
  return NULL;
}

static int
array_field_from_py (GITypeInfo *fti, char *base, size_t offset, PyObject *value)
{
  if (gi_type_info_get_array_type (fti) == GI_ARRAY_TYPE_PTR_ARRAY)
    {
      GIArgument dest = { 0 };
      PyGIArgCleanup cleanup = { 0 };
      if (pygi_garray_from_py (value, fti, GI_TRANSFER_EVERYTHING, &dest, &cleanup) != 0)
        return -1;

      GPtrArray **slot = (GPtrArray **)(void *)(base + offset);
      if (*slot != NULL)
        g_ptr_array_unref (*slot);
      *slot = (GPtrArray *)dest.v_pointer;
      return 0;
    }

  if (gi_type_info_get_array_type (fti) != GI_ARRAY_TYPE_C)
    return -1;

  g_autoptr (GITypeInfo) inner_ti = gi_type_info_get_param_type (fti, 0);
  if (inner_ti == NULL)
    return -1;

  if (gi_type_info_is_zero_terminated (fti))
    {
      GITypeTag itag = gi_type_info_get_tag (inner_ti);
      if (itag == GI_TYPE_TAG_UTF8 || itag == GI_TYPE_TAG_FILENAME)
        {
          PyObject *seq = PySequence_Fast (value, "expected a sequence of strings");
          if (seq == NULL)
            return -1;
          Py_ssize_t len = PySequence_Fast_GET_SIZE (seq);
          gchar **strv = g_new0 (gchar *, (gsize)len + 1);
          for (Py_ssize_t i = 0; i < len; i++)
            {
              PyObject *item = PySequence_Fast_GET_ITEM (seq, i);
              if (!PyUnicode_Check (item))
                {
                  Py_DECREF (seq);
                  g_strfreev (strv);
                  PyErr_SetString (PyExc_TypeError, "expected a sequence of strings");
                  return -1;
                }
              const char *s = PyUnicode_AsUTF8 (item);
              if (s == NULL)
                {
                  Py_DECREF (seq);
                  g_strfreev (strv);
                  return -1;
                }
              strv[i] = g_strdup (s);
            }
          Py_DECREF (seq);
          gchar ***slot = (gchar ***)(void *)(base + offset);
          g_strfreev (*slot);
          *slot = strv;
          return 0;
        }
    }

  size_t fixed = 0;
  if (gi_type_info_get_array_fixed_size (fti, &fixed) && fixed > 0)
    {
      PyObject *seq = PySequence_Fast (value, "expected a sequence");
      if (seq == NULL)
        return -1;
      Py_ssize_t len = PySequence_Fast_GET_SIZE (seq);
      if (len != (Py_ssize_t)fixed)
        {
          Py_DECREF (seq);
          PyErr_Format (PyExc_ValueError,
                        "expected fixed array of length %zu, got %zd",
                        fixed,
                        len);
          return -1;
        }
      PyGIContainerElement element;
      if (pygi_container_element_init (&element, inner_ti) != 0)
        {
          Py_DECREF (seq);
          return -1;
        }
      gsize elem_size = pygi_container_element_inline_size (&element);
      if (elem_size == 0)
        {
          Py_DECREF (seq);
          PyErr_SetString (PyExc_NotImplementedError, "unsupported fixed array element type");
          return -1;
        }
      char *array = base + offset;
      for (size_t i = 0; i < fixed; i++)
        {
          PyObject *item = PySequence_Fast_GET_ITEM (seq, (Py_ssize_t)i);
          if (pygi_container_element_inline_from_py (&element,
                                                     item,
                                                     GI_TRANSFER_NOTHING,
                                                     array + ((gsize)i * elem_size))
              != 0)
            {
              Py_DECREF (seq);
              return -1;
            }
        }
      Py_DECREF (seq);
      return 0;
    }

  PyErr_SetString (PyExc_NotImplementedError, "unsupported array field");
  return -1;
}

PyObject *
field_to_py (GITypeInfo *fti, char *base, size_t offset, PyObject *parent)
{
  GITypeTag ftag = gi_type_info_get_tag (fti);
  if (ftag == GI_TYPE_TAG_VOID)
    {
      gpointer ptr = *(gpointer *)(base + offset);
      if (ptr == NULL)
        Py_RETURN_NONE;
      return PyLong_FromUnsignedLongLong ((unsigned long long)(uintptr_t)ptr);
    }
  if (ftag == GI_TYPE_TAG_ARRAY)
    return array_field_to_py (fti, base, offset, parent);
  if (ftag == GI_TYPE_TAG_GLIST || ftag == GI_TYPE_TAG_GSLIST)
    {
      GIArgument arg = { .v_pointer = *(gpointer *)((void *)(base + offset)) };
      return pygi_argument_to_py_transfer (NULL, fti, &arg, GI_TRANSFER_NOTHING);
    }
  if (ftag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo == NULL)
        return NULL;
      if (GI_IS_ENUM_INFO (finfo) || GI_IS_FLAGS_INFO (finfo))
        {
          GITypeTag stag = gi_enum_info_get_storage_type ((GIEnumInfo *)finfo);
          return pygi_primitive_storage_to_py (stag, base + offset);
        }
      if (GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo))
        {
          GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)finfo);
          gpointer field_ptr = gi_type_info_is_pointer (fti) ? *(gpointer *)(base + offset)
                                                             : (gpointer)(base + offset);
          if (field_ptr == NULL)
            Py_RETURN_NONE;
          PyObject *cls = record_build_class_for_info (finfo, parent);
          if (cls == NULL)
            return NULL;
          PyObject *out = pygi_boxed_new_alias (cls, field_ptr, gtype, parent);
          Py_DECREF (cls);
          return out;
        }
      if (GI_IS_OBJECT_INFO (finfo) || GI_IS_INTERFACE_INFO (finfo))
        {
          gpointer ptr = *(gpointer *)(base + offset);
          if (ptr == NULL)
            Py_RETURN_NONE;
          if (GI_IS_REGISTERED_TYPE_INFO (finfo))
            {
              GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)finfo);
              return pygi_gobject_to_py_as_gtype ((GObject *)ptr, gtype, GI_TRANSFER_NOTHING);
            }
        }
    }

  PyGIType field_type = { 0 };
  if (pygi_type_from_gi (fti, &field_type) == 0 && pygi_type_is_direct_storage (&field_type))
    return pygi_marshal_to_py (&(PyGIMarshalSlot){
        .type = fti,
        .pygi_type = &field_type,
        .transfer = GI_TRANSFER_NOTHING,
        .transfer_set = true,
        .kind = PYGI_MARSHAL_TARGET_MEMORY,
        .target.memory = base + offset,
    });

  PyErr_Format (PyExc_NotImplementedError, "unsupported field type tag %d", (int)ftag);
  return NULL;
}

int
field_from_py (GITypeInfo *fti, char *base, size_t offset, PyObject *value)
{
  GITypeTag ftag = gi_type_info_get_tag (fti);
  if (ftag == GI_TYPE_TAG_GTYPE)
    {
      GType gtype = G_TYPE_INVALID;
      if (pygi_gtype_from_gimeta_attr (value, &gtype) == 0)
        {
          *(GType *)(base + offset) = gtype;
          return 0;
        }

      if (!PyErr_ExceptionMatches (PyExc_AttributeError))
        return -1;
      PyErr_Clear ();
      PyErr_SetString (PyExc_TypeError, "expected GType carrier for GType field");
      return -1;
    }
  if (ftag == GI_TYPE_TAG_ARRAY)
    return array_field_from_py (fti, base, offset, value);
  if (ftag == GI_TYPE_TAG_GLIST || ftag == GI_TYPE_TAG_GSLIST)
    {
      GIArgument dest = { 0 };
      PyGIArgCleanup cleanup = { 0 };
      int rc = (ftag == GI_TYPE_TAG_GLIST)
                   ? pygi_glist_from_py (value, fti, GI_TRANSFER_EVERYTHING, &dest, &cleanup)
                   : pygi_slist_from_py (value, fti, GI_TRANSFER_EVERYTHING, &dest, &cleanup);
      if (rc != 0)
        return -1;

      gpointer *slot = (gpointer *)(void *)(base + offset);
      if (*slot != NULL)
        {
          if (ftag == GI_TYPE_TAG_GLIST)
            g_list_free ((GList *)*slot);
          else
            g_slist_free ((GSList *)*slot);
        }
      *slot = dest.v_pointer;
      return 0;
    }
  if (ftag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) finfo = gi_type_info_get_interface (fti);
      if (finfo != NULL && (GI_IS_ENUM_INFO (finfo) || GI_IS_FLAGS_INFO (finfo)))
        {
          GITypeTag stag = gi_enum_info_get_storage_type ((GIEnumInfo *)finfo);
          return pygi_py_to_primitive_storage (value, stag, base + offset);
        }
      if (finfo != NULL && (GI_IS_STRUCT_INFO (finfo) || GI_IS_UNION_INFO (finfo)))
        {
          if (value == Py_None)
            {
              if (!gi_type_info_is_pointer (fti))
                {
                  PyErr_SetString (PyExc_TypeError, "inline struct fields do not accept None");
                  return -1;
                }
              *(gpointer *)(base + offset) = NULL;
              return 0;
            }

          gpointer boxed_ptr = NULL;
          if (pygi_boxed_get (value, &boxed_ptr) != 0)
            return -1;

          if (gi_type_info_is_pointer (fti))
            {
              *(gpointer *)(base + offset) = boxed_ptr;
              return 0;
            }

          gsize size = record_info_size (finfo);
          if (size == 0)
            {
              PyErr_SetString (PyExc_RuntimeError,
                               "cannot write inline struct field with unknown size");
              return -1;
            }
          memcpy (base + offset, boxed_ptr, size);
          return 0;
        }
    }

  PyGIType field_type = { 0 };
  if (pygi_type_from_gi (fti, &field_type) == 0 && pygi_type_is_direct_storage (&field_type))
    return pygi_marshal_from_py (value,
                                 &(PyGIMarshalSlot){
                                     .type = fti,
                                     .pygi_type = &field_type,
                                     .transfer = GI_TRANSFER_NOTHING,
                                     .transfer_set = true,
                                     .kind = PYGI_MARSHAL_TARGET_MEMORY,
                                     .target.memory = base + offset,
                                 });

  PyErr_Format (PyExc_NotImplementedError, "unsupported field type tag %d", (int)ftag);
  return -1;
}

static PyObject *
event_source_call_method (GSource *source, const char *name, PyObject *args)
{
  PyGIEventSource *event_source = (PyGIEventSource *)source;
  if (event_source->py_wrapper == NULL)
    Py_RETURN_NONE;

  PyObject *method = PyObject_GetAttrString (event_source->py_wrapper, name);
  if (method == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          Py_RETURN_NONE;
        }
      return NULL;
    }

  PyObject *result
      = args == NULL ? PyObject_CallNoArgs (method) : PyObject_CallObject (method, args);
  Py_DECREF (method);
  return result;
}

static gboolean
event_source_result_as_bool (PyObject *result, gboolean fallback)
{
  if (result == Py_None)
    return fallback;

  int truth = PyObject_IsTrue (result);
  if (truth < 0)
    {
      PyErr_Print ();
      return fallback;
    }
  return truth ? TRUE : FALSE;
}

static gboolean
event_source_prepare (GSource *source, gint *timeout_)
{
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *result = event_source_call_method (source, "prepare", NULL);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      if (timeout_ != NULL)
        *timeout_ = -1;
      return FALSE;
    }

  gboolean ready = FALSE;
  gint timeout = -1;
  if (PyTuple_Check (result) && PyTuple_GET_SIZE (result) == 2)
    {
      ready = event_source_result_as_bool (PyTuple_GET_ITEM (result, 0), FALSE);
      long timeout_long = PyLong_AsLong (PyTuple_GET_ITEM (result, 1));
      if (timeout_long == -1 && PyErr_Occurred ())
        PyErr_Print ();
      else
        timeout = (gint)timeout_long;
    }
  else
    ready = event_source_result_as_bool (result, FALSE);

  if (timeout_ != NULL)
    *timeout_ = timeout;
  Py_DECREF (result);
  PyGILState_Release (state);
  return ready;
}

static gboolean
event_source_check (GSource *source)
{
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *result = event_source_call_method (source, "check", NULL);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return FALSE;
    }
  gboolean ready = event_source_result_as_bool (result, FALSE);
  Py_DECREF (result);
  PyGILState_Release (state);
  return ready;
}

static gboolean
event_source_dispatch (GSource *source, GSourceFunc callback, gpointer user_data)
{
  (void)callback;
  (void)user_data;
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *dispatch_args = Py_BuildValue ("(OO)", Py_None, Py_None);
  if (dispatch_args == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return G_SOURCE_REMOVE;
    }

  PyObject *result = event_source_call_method (source, "dispatch", dispatch_args);
  Py_DECREF (dispatch_args);
  if (result == NULL)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return G_SOURCE_REMOVE;
    }

  gboolean keep = event_source_result_as_bool (result, G_SOURCE_REMOVE);
  Py_DECREF (result);
  PyGILState_Release (state);
  return keep ? G_SOURCE_CONTINUE : G_SOURCE_REMOVE;
}

static GSourceFuncs event_source_funcs = {
  .prepare = event_source_prepare,
  .check = event_source_check,
  .dispatch = event_source_dispatch,
  .finalize = NULL,
};

PyObject *
py_glib_event_source_new (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  if (!PyArg_ParseTuple (args, "O", &cls))
    return NULL;
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "glib_event_source_new: cls must be a type");
      return NULL;
    }

  GSource *source = g_source_new (&event_source_funcs, sizeof (PyGIEventSource));
  if (source == NULL)
    return PyErr_NoMemory ();

  PyObject *self = pygi_boxed_new (cls, source, g_source_get_type (), 1);
  if (self == NULL)
    {
      g_source_unref (source);
      return NULL;
    }
  ((PyGIEventSource *)source)->py_wrapper = self;
  return self;
}

static size_t
record_anonymous_union_offset (GIBaseInfo *info, const char *previous_field_name, size_t align)
{
  GIFieldInfo *field = NULL;
  if (!record_lookup_field (info, previous_field_name, &field))
    {
      PyErr_Format (PyExc_AttributeError,
                    "%s has no field %s",
                    gi_base_info_get_name (info),
                    previous_field_name);
      return 0;
    }

  size_t offset = gi_field_info_get_offset (field);
  size_t size_bits = gi_field_info_get_size (field);
  gi_base_info_unref ((GIBaseInfo *)field);

  size_t size = (size_bits + 7u) / 8u;
  if (size == 0)
    size = 1;

  size_t end = offset + size;
  size_t mask = align - 1u;
  if ((align & mask) == 0)
    end = (end + mask) & ~mask;
  else
    {
      size_t rem = end % align;
      if (rem != 0)
        end += align - rem;
    }

  return end;
}

/* record_field_names(info) -> tuple[str, ...]
 * The readable primitive-scalar field names of a struct/union, in declaration
 * order. Used to set __match_args__ so records support positional pattern
 * matching, e.g. `case Color(red, green, blue)` — where field order is the
 * natural contract, mirroring the C layout.
 *
 * Restricted to readable primitive scalars: those are the safe, value-like
 * fields. Pointer/array/nested/interface fields are excluded — a positional
 * `case` reads *every* listed attribute, and routing those through the generic
 * field getter can fault on a freshly-zeroed record (e.g. a NULL gpointer
 * field). */
static PyObject *
py_record_field_names (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *capsule = NULL;
  PyObject *cls = NULL;
  if (!PyArg_ParseTuple (args, "O|O", &capsule, &cls))
    return NULL;
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  if (!GI_IS_STRUCT_INFO (info) && !GI_IS_UNION_INFO (info))
    return PyTuple_New (0);

  int n = gi_struct_or_union_n_fields (info);
  PyObject *names = PyList_New (0);
  if (names == NULL)
    return NULL;
  for (int fi = 0; fi < n; fi++)
    {
      g_autoptr (GIFieldInfo) field = (GIFieldInfo *)gi_struct_or_union_get_field (info, (guint)fi);
      if (field == NULL)
        continue;
      if (!(gi_field_info_get_flags (field) & GI_FIELD_IS_READABLE))
        continue;
      g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
      if (fti == NULL)
        continue;
      if (!field_to_py_supported (fti))
        continue;
      switch (gi_type_info_get_tag (fti))
        {
        case GI_TYPE_TAG_BOOLEAN:
        case GI_TYPE_TAG_INT8:
        case GI_TYPE_TAG_UINT8:
        case GI_TYPE_TAG_INT16:
        case GI_TYPE_TAG_UINT16:
        case GI_TYPE_TAG_INT32:
        case GI_TYPE_TAG_UINT32:
        case GI_TYPE_TAG_INT64:
        case GI_TYPE_TAG_UINT64:
        case GI_TYPE_TAG_FLOAT:
        case GI_TYPE_TAG_DOUBLE:
          break;
        default:
          continue; /* skip non-primitive fields (see comment above) */
        }
      const char *raw_name = gi_base_info_get_name ((GIBaseInfo *)field);
      if (raw_name == NULL)
        continue;
      if (cls != NULL)
        {
          int reserved = record_class_field_name_reserved (cls, raw_name);
          if (reserved < 0)
            {
              Py_DECREF (names);
              return NULL;
            }
          if (reserved)
            continue;
        }
      PyObject *s = PyUnicode_FromString (raw_name);
      if (s == NULL)
        {
          Py_DECREF (names);
          return NULL;
        }
      int rc = PyList_Append (names, s);
      Py_DECREF (s);
      if (rc != 0)
        {
          Py_DECREF (names);
          return NULL;
        }
    }
  PyObject *tuple = PyList_AsTuple (names);
  Py_DECREF (names);
  return tuple;
}

/* StructInfo.anonymous_union_offset(prev_field, align) /
 * UnionInfo.anonymous_union_offset(...) — byte offset at which an anonymous
 * union following `prev_field` begins. METH_VARARGS method on both types. */
PyObject *
ginext_anonymous_union_offset_method (PyObject *self, PyObject *args)
{
  const char *previous_field_name = NULL;
  Py_ssize_t align = 1;
  if (!PyArg_ParseTuple (args, "sn", &previous_field_name, &align))
    return NULL;
  if (align <= 0)
    align = 1;
  GIBaseInfo *info = PYGI_INFO (self);
  size_t end = record_anonymous_union_offset (info, previous_field_name, (size_t)align);
  if (PyErr_Occurred ())
    return NULL;
  return PyLong_FromSize_t (end);
}

static PyObject *
py_register_boxed_class (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  unsigned long long gtype_arg = 0;
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "OKO", &cls, &gtype_arg, &capsule))
    return NULL;
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "register_boxed_class: cls must be a type");
      return NULL;
    }
  if (boxed_classes_by_gtype == NULL)
    {
      boxed_classes_by_gtype = PyDict_New ();
      if (boxed_classes_by_gtype == NULL)
        return NULL;
    }
  if (gtype_arg != 0)
    {
      PyObject *profile_name = profile_name_from_object (cls);
      if (profile_name == NULL)
        return NULL;
      PyObject *key = boxed_registry_key ((GType)gtype_arg, profile_name);
      Py_DECREF (profile_name);
      if (key == NULL)
        return NULL;
      if (PyDict_SetItem (boxed_classes_by_gtype, key, cls) < 0)
        {
          Py_DECREF (key);
          return NULL;
        }
      Py_DECREF (key);
    }
  (void)capsule;
  Py_RETURN_NONE;
}

PyObject *
py_record_setup_class (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "OO", &cls, &capsule))
    return NULL;
  if (!PyType_Check (cls))
    {
      PyErr_SetString (PyExc_TypeError, "record_setup_class: cls must be a type");
      return NULL;
    }
  GIBaseInfo *info = info_from_capsule (capsule);
  if (info == NULL)
    return NULL;
  if (!GI_IS_STRUCT_INFO (info) && !GI_IS_UNION_INFO (info))
    {
      PyErr_SetString (PyExc_TypeError, "record_setup_class: expected struct or union info");
      return NULL;
    }

  PyGIRecordClassData *existing_data = record_class_data_for_type ((PyTypeObject *)cls);
  if (existing_data == NULL && PyErr_Occurred ())
    return NULL;

  GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)info);
  if (existing_data == NULL)
    {
      PyGIRecordClassData *data = g_new0 (PyGIRecordClassData, 1);
      data->info = gi_base_info_ref (info);
      data->gtype = gtype;
      data->size = record_info_size (info);

      PyObject *data_capsule
          = PyCapsule_New (data, PYGI_RECORD_CLASS_DATA_CAPSULE, record_class_data_destroy);
      if (data_capsule == NULL)
        {
          gi_base_info_unref (data->info);
          g_free (data);
          return NULL;
        }
      if (PyObject_SetAttrString (cls, "__record_data__", data_capsule) < 0)
        {
          Py_DECREF (data_capsule);
          return NULL;
        }
      Py_DECREF (data_capsule);

      PyObject *setup_args = PyTuple_Pack (2, cls, capsule);
      if (setup_args == NULL)
        return NULL;
      PyObject *installed = py_record_install_field_descriptors (NULL, setup_args);
      Py_DECREF (setup_args);
      if (installed == NULL)
        return NULL;
      Py_DECREF (installed);

      PyObject *names_args = PyTuple_Pack (2, capsule, cls);
      if (names_args == NULL)
        return NULL;
      PyObject *match_args = py_record_field_names (NULL, names_args);
      Py_DECREF (names_args);
      if (match_args == NULL)
        return NULL;
      if (PyTuple_GET_SIZE (match_args) > 0
          && PyObject_SetAttrString (cls, "__match_args__", match_args) < 0)
        {
          Py_DECREF (match_args);
          return NULL;
        }
      Py_DECREF (match_args);
    }

  PyObject *register_args = Py_BuildValue ("OKO", cls, (unsigned long long)gtype, capsule);
  if (register_args == NULL)
    return NULL;
  PyObject *registered = py_register_boxed_class (NULL, register_args);
  Py_DECREF (register_args);
  if (registered == NULL)
    return NULL;
  Py_DECREF (registered);

  Py_RETURN_NONE;
}

void
pygi_pybuffer_release_destroy_notify (gpointer data)
{
  Py_buffer *view = (Py_buffer *)data;
  if (view != NULL)
    {
      PyBuffer_Release (view);
      g_free (view);
    }
}
