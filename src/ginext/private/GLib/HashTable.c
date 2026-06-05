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

/* hashtable.c - GHashTable argument and return marshalling. */
#include "GLib/HashTable.h"

#include "GLib/Variant.h"
#include "GObject/Boxed.h"
#include "GObject/Object-info.h"
#include "marshal/container-element.h"
#include "marshal/gvalue.h"
#include "marshal/marshal.h"
#include "runtime/type-info.h"

typedef struct
{
  gboolean is_variant;
  gboolean is_object;
  gboolean is_struct; /* struct or union (boxed pointer) */
} PyGIHashSlotKind;

static void
hash_slot_kind_init (PyGIHashSlotKind *out, GITypeInfo *ti)
{
  *out = (PyGIHashSlotKind){ 0 };
  if (ti == NULL)
    return;
  if (gi_type_info_is_variant (ti))
    {
      out->is_variant = TRUE;
      return;
    }
  if (gi_type_info_get_tag (ti) != GI_TYPE_TAG_INTERFACE)
    return;
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL)
    return;
  if (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface))
    out->is_object = TRUE;
  else if (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
    out->is_struct = TRUE;
}

static gboolean
hash_slot_kind_uses_container_element (const PyGIHashSlotKind *kind)
{
  return !kind->is_variant && !kind->is_object && !kind->is_struct;
}

static gboolean
hash_table_is_opaque (GITypeInfo *ti)
{
  g_autoptr (GITypeInfo) key_ti = gi_type_info_get_param_type (ti, 0);
  g_autoptr (GITypeInfo) value_ti = gi_type_info_get_param_type (ti, 1);
  if (key_ti == NULL || value_ti == NULL)
    return TRUE;
  return gi_type_info_get_tag (value_ti) == GI_TYPE_TAG_VOID
         || gi_type_info_get_tag (key_ti) == GI_TYPE_TAG_VOID;
}

static gboolean
hash_element_is_wide_boxed (const PyGIContainerElement *element)
{
  switch (element->type.kind)
    {
    case PYGI_TYPE_DOUBLE:
    case PYGI_TYPE_FLOAT:
    case PYGI_TYPE_INT64:
    case PYGI_TYPE_UINT64:
      return TRUE;
    default:
      return FALSE;
    }
}

static GDestroyNotify
hash_element_destroy_notify (const PyGIContainerElement *element, GITransfer transfer)
{
  if (hash_element_is_wide_boxed (element))
    return g_free;
  if (element->is_string && transfer == GI_TRANSFER_EVERYTHING)
    return g_free;
  return NULL;
}

static void
hash_gvalue_destroy_notify (gpointer data)
{
  GValue *value = (GValue *)data;
  if (value != NULL)
    {
      g_value_unset (value);
      g_free (value);
    }
}

static gboolean
hash_key_uses_string_hash (const PyGIContainerElement *key)
{
  return key->is_string;
}

static int
hash_table_elements_init (GITypeInfo *ti,
                          PyGIContainerElement *key,
                          PyGIContainerElement *value,
                          PyGIHashSlotKind *key_kind,
                          PyGIHashSlotKind *value_kind,
                          gboolean *value_is_gvalue,
                          gboolean *value_is_hash)
{
  g_autoptr (GITypeInfo) key_ti = gi_type_info_get_param_type (ti, 0);
  g_autoptr (GITypeInfo) value_ti = gi_type_info_get_param_type (ti, 1);
  if (key_ti == NULL || value_ti == NULL)
    {
      PyErr_SetString (PyExc_NotImplementedError, "GHashTable element type metadata missing");
      return -1;
    }
  *value_is_gvalue = gi_type_info_is_gvalue (value_ti);
  *value_is_hash = gi_type_info_get_tag (value_ti) == GI_TYPE_TAG_GHASH;
  hash_slot_kind_init (key_kind, key_ti);
  hash_slot_kind_init (value_kind, value_ti);
  if (hash_slot_kind_uses_container_element (key_kind)
      && (pygi_container_element_init (key, key_ti) != 0
          || !pygi_container_element_can_use_hash_pointer (key)
          || hash_element_is_wide_boxed (key)))
    {
      PyErr_SetString (PyExc_NotImplementedError, "GHashTable element type is not supported");
      return -1;
    }
  if (!*value_is_gvalue && !*value_is_hash && hash_slot_kind_uses_container_element (value_kind)
      && (pygi_container_element_init (value, value_ti) != 0
          || !pygi_container_element_can_use_hash_pointer (value)))
    {
      PyErr_SetString (PyExc_NotImplementedError, "GHashTable element type is not supported");
      return -1;
    }
  return 0;
}

PyObject *
pygi_ghash_to_py (GICallableInfo *cb G_GNUC_UNUSED,
                  GITypeInfo *ti,
                  GIArgument *arg,
                  GITransfer transfer)
{
  g_return_val_if_fail (ti != NULL, NULL);
  g_return_val_if_fail (GI_IS_TYPE_INFO (ti), NULL);
  g_return_val_if_fail (arg != NULL, NULL);

  GHashTable *hash = (GHashTable *)arg->v_pointer;
  if (hash == NULL)
    Py_RETURN_NONE;

  if (hash_table_is_opaque (ti))
    {
      /* Opaque return: we'd need a GLib.HashTable boxed wrapper to
       * hand back; that wiring is out of the current invoke slice.
       * Reject cleanly at runtime so the caller gets a clear error
       * instead of a crash. The validation gate still accepts the
       * shape so descriptor build succeeds for inventory purposes. */
      if (transfer != GI_TRANSFER_NOTHING)
        g_hash_table_unref (hash);
      PyErr_SetString (PyExc_NotImplementedError,
                       "opaque GHashTable return (no element-type metadata) "
                       "is outside the current ginext invoke slice");
      return NULL;
    }

  PyGIContainerElement key = { 0 };
  PyGIContainerElement value = { 0 };
  PyGIHashSlotKind key_kind = { 0 };
  PyGIHashSlotKind value_kind = { 0 };
  gboolean value_is_gvalue = FALSE;
  gboolean value_is_hash = FALSE;
  if (hash_table_elements_init (ti,
                                &key,
                                &value,
                                &key_kind,
                                &value_kind,
                                &value_is_gvalue,
                                &value_is_hash)
      != 0)
    return NULL;
  g_autoptr (GITypeInfo) key_ti = NULL;
  g_autoptr (GITypeInfo) value_ti = NULL;
  if (!hash_slot_kind_uses_container_element (&key_kind))
    key_ti = gi_type_info_get_param_type (ti, 0);
  if (!hash_slot_kind_uses_container_element (&value_kind) || value_is_hash)
    {
      value_ti = gi_type_info_get_param_type (ti, 1);
      if (value_is_hash && value_ti == NULL)
        {
          PyErr_SetString (PyExc_NotImplementedError,
                           "nested GHashTable value type metadata missing");
          return NULL;
        }
    }

  PyObject *dict = PyDict_New ();
  if (dict == NULL)
    return NULL;

  GHashTableIter iter;
  gpointer k = NULL;
  gpointer v = NULL;
  g_hash_table_iter_init (&iter, hash);
  while (g_hash_table_iter_next (&iter, &k, &v))
    {
      PyObject *py_key = NULL;
      if (key_kind.is_variant)
        {
          GIArgument key_arg = { .v_pointer = k };
          py_key = pygi_variant_to_py (key_ti, &key_arg, GI_TRANSFER_NOTHING);
        }
      else if (key_kind.is_object)
        {
          GIArgument key_arg = { .v_pointer = k };
          py_key = pygi_argument_to_py_transfer (cb, key_ti, &key_arg, GI_TRANSFER_NOTHING);
        }
      else if (key_kind.is_struct)
        {
          GIArgument key_arg = { .v_pointer = k };
          py_key = pygi_argument_to_py_transfer (cb, key_ti, &key_arg, GI_TRANSFER_NOTHING);
        }
      else
        py_key = pygi_container_element_hash_pointer_to_py (&key, k);
      if (py_key == NULL)
        {
          Py_DECREF (dict);
          return NULL;
        }
      PyObject *py_value = NULL;
      if (value_is_gvalue)
        py_value = pygi_gvalue_value_to_py ((GValue *)v);
      else if (value_kind.is_variant)
        {
          GIArgument variant_arg = { .v_pointer = v };
          py_value = pygi_variant_to_py (value_ti, &variant_arg, GI_TRANSFER_NOTHING);
        }
      else if (value_kind.is_object || value_kind.is_struct)
        {
          GIArgument val_arg = { .v_pointer = v };
          py_value = pygi_argument_to_py_transfer (cb, value_ti, &val_arg, GI_TRANSFER_NOTHING);
        }
      else if (value_is_hash)
        {
          GIArgument nested_arg = { .v_pointer = v };
          py_value = pygi_ghash_to_py (cb, value_ti, &nested_arg, GI_TRANSFER_NOTHING);
        }
      else
        py_value = pygi_container_element_hash_pointer_to_py (&value, v);
      if (py_value == NULL)
        {
          Py_DECREF (py_key);
          Py_DECREF (dict);
          return NULL;
        }
      int rc = PyDict_SetItem (dict, py_key, py_value);
      Py_DECREF (py_value);
      Py_DECREF (py_key);
      if (rc != 0)
        {
          Py_DECREF (dict);
          return NULL;
        }
    }

  if (transfer != GI_TRANSFER_NOTHING)
    g_hash_table_unref (hash);
  return dict;
}

int
pygi_ghash_from_py (PyObject *value_obj,
                    GITypeInfo *ti,
                    GITransfer transfer,
                    GIArgument *dest,
                    PyGIArgCleanup *cleanup)
{
  g_return_val_if_fail (ti != NULL, -1);
  g_return_val_if_fail (GI_IS_TYPE_INFO (ti), -1);
  g_return_val_if_fail (dest != NULL, -1);
  g_return_val_if_fail (cleanup != NULL, -1);

  if (value_obj == Py_None)
    {
      dest->v_pointer = NULL;
      return 0;
    }

  if (hash_table_is_opaque (ti))
    {
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (value_obj, &boxed_ptr) == 0)
        {
          dest->v_pointer = boxed_ptr;
          return 0;
        }
      PyErr_Clear ();
      PyErr_SetString (PyExc_TypeError,
                       "GHashTable argument with no element-type metadata "
                       "accepts only None or a GLib.HashTable instance");
      return -1;
    }

  PyGIContainerElement key = { 0 };
  PyGIContainerElement value = { 0 };
  PyGIHashSlotKind key_kind = { 0 };
  PyGIHashSlotKind value_kind = { 0 };
  gboolean value_is_gvalue = FALSE;
  gboolean value_is_hash = FALSE;
  if (hash_table_elements_init (ti,
                                &key,
                                &value,
                                &key_kind,
                                &value_kind,
                                &value_is_gvalue,
                                &value_is_hash)
      != 0)
    return -1;
  if (value_is_hash)
    {
      PyErr_SetString (PyExc_NotImplementedError, "GHashTable nested value input is not supported");
      return -1;
    }

  PyObject *items = PyMapping_Items (value_obj);
  if (items == NULL)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          PyErr_SetString (PyExc_TypeError, "GHashTable argument must be a mapping");
        }
      return -1;
    }

  GHashFunc key_hash_func = g_direct_hash;
  GEqualFunc key_equal_func = g_direct_equal;
  if (hash_slot_kind_uses_container_element (&key_kind) && hash_key_uses_string_hash (&key))
    {
      key_hash_func = g_str_hash;
      key_equal_func = g_str_equal;
    }
  else if (key_kind.is_variant)
    {
      key_hash_func = (GHashFunc)g_variant_hash;
      key_equal_func = (GEqualFunc)g_variant_equal;
    }

  GDestroyNotify key_destroy
      = key_kind.is_variant
            ? (transfer != GI_TRANSFER_NOTHING ? (GDestroyNotify)g_variant_unref : NULL)
            : (key_kind.is_object
                   ? (transfer != GI_TRANSFER_NOTHING ? g_object_unref : NULL)
                   : (key_kind.is_struct ? NULL : hash_element_destroy_notify (&key, transfer)));

  GDestroyNotify value_destroy
      = value_is_gvalue
            ? hash_gvalue_destroy_notify
            : (value_kind.is_variant
                   ? (transfer != GI_TRANSFER_NOTHING ? (GDestroyNotify)g_variant_unref : NULL)
                   : (value_kind.is_object
                          ? (transfer != GI_TRANSFER_NOTHING ? g_object_unref : NULL)
                          : (value_kind.is_struct
                                 ? NULL
                                 : hash_element_destroy_notify (&value, transfer))));
  GHashTable *hash
      = g_hash_table_new_full (key_hash_func, key_equal_func, key_destroy, value_destroy);
  if (hash == NULL)
    {
      Py_DECREF (items);
      PyErr_NoMemory ();
      return -1;
    }

  Py_ssize_t n = PyList_GET_SIZE (items);
  for (Py_ssize_t i = 0; i < n; i++)
    {
      PyObject *pair = PyList_GET_ITEM (items, i);
      if (!PyTuple_Check (pair) || PyTuple_GET_SIZE (pair) != 2)
        {
          Py_DECREF (items);
          g_hash_table_unref (hash);
          PyErr_SetString (PyExc_TypeError, "mapping items must be key/value pairs");
          return -1;
        }

      GIArgument key_arg = { 0 };
      GIArgument value_arg = { 0 };
      gpointer key_ptr = NULL;
      gpointer value_ptr = NULL;
      GValue *gvalue_ptr = NULL;
      PyObject *py_key_item = PyTuple_GET_ITEM (pair, 0);
      if (key_kind.is_variant)
        {
          if (pygi_py_item_to_gvariant (py_key_item, &key_ptr) != 0)
            {
              Py_DECREF (items);
              g_hash_table_unref (hash);
              return -1;
            }
        }
      else if (key_kind.is_object)
        {
          GIArgument tmp = { 0 };
          if (pygi_object_info_from_py (py_key_item, &tmp) != 0)
            {
              Py_DECREF (items);
              g_hash_table_unref (hash);
              return -1;
            }
          if (transfer != GI_TRANSFER_NOTHING && tmp.v_pointer != NULL)
            g_object_ref ((GObject *)tmp.v_pointer);
          key_ptr = tmp.v_pointer;
        }
      else if (key_kind.is_struct)
        {
          if (pygi_boxed_get (py_key_item, &key_ptr) != 0)
            {
              Py_DECREF (items);
              g_hash_table_unref (hash);
              return -1;
            }
        }
      else if (pygi_container_element_argument_from_py (&key, py_key_item, &key_arg) != 0
               || pygi_container_element_hash_pointer_from_argument (&key,
                                                                     &key_arg,
                                                                     transfer,
                                                                     &key_ptr)
                      != 0)
        {
          Py_DECREF (items);
          g_hash_table_unref (hash);
          return -1;
        }
      if (value_is_gvalue)
        {
          gvalue_ptr = g_new0 (GValue, 1);
          if (gvalue_ptr == NULL)
            {
              Py_DECREF (items);
              g_hash_table_unref (hash);
              PyErr_NoMemory ();
              return -1;
            }
          if (pygi_py_to_gvalue_inplace (PyTuple_GET_ITEM (pair, 1), gvalue_ptr, NULL) != 0)
            {
              g_free (gvalue_ptr);
              Py_DECREF (items);
              g_hash_table_unref (hash);
              return -1;
            }
          value_ptr = gvalue_ptr;
        }
      else if (value_kind.is_variant)
        {
          if (pygi_py_item_to_gvariant (PyTuple_GET_ITEM (pair, 1), &value_ptr) != 0)
            {
              Py_DECREF (items);
              g_hash_table_unref (hash);
              return -1;
            }
        }
      else if (value_kind.is_object)
        {
          GIArgument tmp = { 0 };
          if (pygi_object_info_from_py (PyTuple_GET_ITEM (pair, 1), &tmp) != 0)
            {
              Py_DECREF (items);
              g_hash_table_unref (hash);
              return -1;
            }
          if (transfer != GI_TRANSFER_NOTHING && tmp.v_pointer != NULL)
            g_object_ref ((GObject *)tmp.v_pointer);
          value_ptr = tmp.v_pointer;
        }
      else if (value_kind.is_struct)
        {
          if (pygi_boxed_get (PyTuple_GET_ITEM (pair, 1), &value_ptr) != 0)
            {
              Py_DECREF (items);
              g_hash_table_unref (hash);
              return -1;
            }
        }
      else if (pygi_container_element_argument_from_py (&value,
                                                        PyTuple_GET_ITEM (pair, 1),
                                                        &value_arg)
                   != 0
               || pygi_container_element_hash_pointer_from_argument (&value,
                                                                     &value_arg,
                                                                     transfer,
                                                                     &value_ptr)
                      != 0)
        {
          Py_DECREF (items);
          g_hash_table_unref (hash);
          return -1;
        }
      g_hash_table_insert (hash, key_ptr, value_ptr);
    }

  Py_DECREF (items);
  dest->v_pointer = hash;
  if (transfer == GI_TRANSFER_NOTHING)
    {
      cleanup->kind = PYGI_ARG_CLEANUP_HASH_TABLE;
      cleanup->ptr = hash;
    }
  return 0;
}
