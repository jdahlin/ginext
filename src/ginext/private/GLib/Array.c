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

/* array.c - Non-C GI_TYPE_TAG_ARRAY (GArray, GPtrArray, GByteArray). */
#include "GLib/Array.h"
#include "common.h"
#include "GObject/Boxed.h"
#include "GObject/Object-info.h"
#include "marshal/container-element.h"
#include "marshal/marshal.h"
#include "marshal/scalar.h"
#include "runtime/type-info.h"

#include <stdint.h>
#include <string.h>

/**
 * garray_elem_size:
 * @elem_ti: GI metadata for the array element
 * @iface: resolved interface metadata for @elem_ti, or %NULL
 *
 * Returns the inline element size for a GArray element. Direct-storage
 * elements use the shared container-element sizing path; unsupported
 * interface elements fall back to pointer-sized slots.
 */
static gsize
garray_elem_size (GITypeInfo *elem_ti, GIBaseInfo *iface)
{
  PyGIContainerElement element;
  if (pygi_container_element_init (&element, elem_ti) == 0)
    {
      gsize size = pygi_container_element_inline_size (&element);
      if (size != 0)
        return size;
    }

  if (gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_INTERFACE && iface != NULL
      && !GI_IS_ENUM_INFO (iface) && !GI_IS_FLAGS_INFO (iface))
    return sizeof (gpointer);

  return 0;
}

/**
 * element_storage_tag_for_legacy_to_py:
 * @elem_ti: GI metadata for the array element
 * @iface: resolved interface metadata for @elem_ti, or %NULL
 *
 * Returns the scalar storage tag used by the legacy primitive_to_py()
 * fallback. Enum and flags interfaces are stored as gint32.
 */
static GITypeTag
element_storage_tag_for_legacy_to_py (GITypeInfo *elem_ti, GIBaseInfo *iface)
{
  GITypeTag tag = gi_type_info_get_tag (elem_ti);
  if (tag == GI_TYPE_TAG_INTERFACE && iface != NULL
      && (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)))
    return GI_TYPE_TAG_INT32;
  return tag;
}

int
pygi_garray_from_py (PyObject *value,
                     GITypeInfo *ti,
                     GITransfer transfer,
                     GIArgument *dest,
                     PyGIArgCleanup *cleanup)
{
  g_return_val_if_fail (ti != NULL, -1);
  g_return_val_if_fail (GI_IS_TYPE_INFO (ti), -1);
  g_return_val_if_fail (dest != NULL, -1);
  g_return_val_if_fail (cleanup != NULL, -1);

  GIArrayType array_type = gi_type_info_get_array_type (ti);
  g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (ti, 0);
  if (elem_ti == NULL && array_type != GI_ARRAY_TYPE_PTR_ARRAY)
    {
      PyErr_SetString (PyExc_NotImplementedError, "array element type metadata missing");
      return -1;
    }

  GITypeTag elem_tag = elem_ti != NULL ? gi_type_info_get_tag (elem_ti) : GI_TYPE_TAG_VOID;

  if (array_type == GI_ARRAY_TYPE_BYTE_ARRAY)
    {
      Py_buffer view;
      const guint8 *src = NULL;
      Py_ssize_t n = 0;
      int got_buffer = 0;
      if (PyObject_CheckBuffer (value) && PyObject_GetBuffer (value, &view, PyBUF_SIMPLE) == 0)
        {
          src = (const guint8 *)view.buf;
          n = view.len;
          got_buffer = 1;
        }
      else
        {
          PyObject *fast = PySequence_Fast (value, "expected bytes-like or sequence of ints");
          if (fast == NULL)
            return -1;
          n = PySequence_Fast_GET_SIZE (fast);
          GByteArray *ba = g_byte_array_sized_new ((guint)n);
          for (Py_ssize_t k = 0; k < n; k++)
            {
              PyObject *item = PySequence_Fast_GET_ITEM (fast, k);
              long v = PyLong_AsLong (item);
              if (v == -1 && PyErr_Occurred ())
                {
                  Py_DECREF (fast);
                  g_byte_array_unref (ba);
                  return -1;
                }
              guint8 b = (guint8)v;
              g_byte_array_append (ba, &b, 1);
            }
          Py_DECREF (fast);
          dest->v_pointer = ba;
          cleanup->kind = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_GBYTE_ARRAY
                                                            : PYGI_ARG_CLEANUP_NONE;
          cleanup->ptr = ba;
          return 0;
        }

      GByteArray *ba = g_byte_array_sized_new ((guint)n);
      g_byte_array_append (ba, src, (guint)n);
      if (got_buffer)
        PyBuffer_Release (&view);
      dest->v_pointer = ba;
      cleanup->kind = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_GBYTE_ARRAY
                                                        : PYGI_ARG_CLEANUP_NONE;
      cleanup->ptr = ba;
      return 0;
    }

  Py_AUTO_DECREF PyObject *fast = PySequence_Fast (value, "expected a sequence");
  if (fast == NULL)
    return -1;
  Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);

  if (array_type == GI_ARRAY_TYPE_PTR_ARRAY)
    {
      if (n == 0)
        {
          GPtrArray *pa = g_ptr_array_new ();
          dest->v_pointer = pa;
          cleanup->kind = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_GPTR_ARRAY
                                                            : PYGI_ARG_CLEANUP_NONE;
          cleanup->ptr = pa;
          return 0;
        }
      g_autoptr (GIBaseInfo) iface = NULL;
      gboolean is_object_elem = FALSE;
      gboolean is_boxed_elem = FALSE;
      if (elem_tag == GI_TYPE_TAG_INTERFACE)
        {
          iface = gi_type_info_get_interface (elem_ti);
          is_object_elem
              = iface != NULL && (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface));
          is_boxed_elem = iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface));
        }
      if (elem_tag != GI_TYPE_TAG_UTF8 && elem_tag != GI_TYPE_TAG_FILENAME && !is_object_elem
          && !is_boxed_elem)
        {
          PyErr_SetString (PyExc_NotImplementedError, "GPtrArray element type not supported");
          return -1;
        }
      if (is_object_elem || is_boxed_elem)
        {
          GPtrArray *pa = g_ptr_array_new_full ((guint)n, NULL);
          for (Py_ssize_t k = 0; k < n; k++)
            {
              PyObject *item = PySequence_Fast_GET_ITEM (fast, k);
              GIArgument tmp = { 0 };
              if (is_object_elem)
                {
                  if (pygi_object_info_from_py (item, &tmp) != 0)
                    {
                      g_ptr_array_unref (pa);
                      return -1;
                    }
                }
              else
                {
                  if (pygi_boxed_get (item, &tmp.v_pointer) != 0)
                    {
                      g_ptr_array_unref (pa);
                      return -1;
                    }
                }
              g_ptr_array_add (pa, tmp.v_pointer);
            }
          dest->v_pointer = pa;
          cleanup->kind = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_GPTR_ARRAY
                                                            : PYGI_ARG_CLEANUP_NONE;
          cleanup->ptr = pa;
          return 0;
        }
      PyGIContainerElement element;
      if (pygi_container_element_init (&element, elem_ti) != 0 || !element.is_string
          || !pygi_container_element_can_use_pointer_slot (&element))
        {
          PyErr_SetString (PyExc_NotImplementedError, "GPtrArray element type not supported");
          return -1;
        }
      GPtrArray *pa
          = g_ptr_array_new_full ((guint)n, (transfer == GI_TRANSFER_EVERYTHING) ? g_free : NULL);
      for (Py_ssize_t k = 0; k < n; k++)
        {
          PyObject *item = PySequence_Fast_GET_ITEM (fast, k);
          gpointer ptr = NULL;
          if (pygi_container_element_pointer_from_py (&element, item, transfer, &ptr) != 0)
            {
              g_ptr_array_unref (pa);
              return -1;
            }
          g_ptr_array_add (pa, ptr);
        }
      dest->v_pointer = pa;
      cleanup->kind
          = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_GPTR_ARRAY : PYGI_ARG_CLEANUP_NONE;
      cleanup->ptr = pa;
      return 0;
    }

  /* Opaque-element GArray (nested container or unrecognized shape):
   * accept None or a boxed wrapper only. */
  if (elem_tag == GI_TYPE_TAG_ARRAY || elem_tag == GI_TYPE_TAG_GLIST
      || elem_tag == GI_TYPE_TAG_GSLIST || elem_tag == GI_TYPE_TAG_GHASH)
    {
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (value, &boxed_ptr) == 0)
        {
          dest->v_pointer = boxed_ptr;
          cleanup->kind = PYGI_ARG_CLEANUP_NONE;
          return 0;
        }
      PyErr_Clear ();
      PyErr_SetString (PyExc_TypeError,
                       "GArray of nested container accepts only None "
                       "or a boxed GLib.Array instance");
      return -1;
    }

  PyGIContainerElement element;
  if (pygi_container_element_init (&element, elem_ti) != 0)
    {
      PyErr_SetString (PyExc_NotImplementedError, "GArray element type not supported");
      return -1;
    }
  gsize elem_size = pygi_container_element_inline_size (&element);
  if (elem_size == 0)
    {
      PyErr_SetString (PyExc_NotImplementedError, "GArray element type not supported");
      return -1;
    }

  GArray *ga = g_array_sized_new (FALSE, FALSE, (guint)elem_size, (guint)n);
  for (Py_ssize_t k = 0; k < n; k++)
    {
      char buf[16];
      if (pygi_container_element_inline_from_py (&element,
                                                 PySequence_Fast_GET_ITEM (fast, k),
                                                 transfer,
                                                 buf)
          != 0)
        {
          g_array_unref (ga);
          return -1;
        }
      g_array_append_vals (ga, buf, 1);
    }
  dest->v_pointer = ga;
  cleanup->kind
      = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_GARRAY : PYGI_ARG_CLEANUP_NONE;
  cleanup->ptr = ga;
  return 0;
}

static PyObject *
primitive_to_py (GITypeTag tag, const void *src)
{
  switch (tag)
    {
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      {
        const char *s = *(const char *const *)src;
        return s != NULL ? PyUnicode_FromString (s) : Py_XNewRef (Py_None);
      }
    case GI_TYPE_TAG_INTERFACE:
      {
        const void *p = *(const void *const *)src;
        return p != NULL ? PyLong_FromUnsignedLongLong ((unsigned long long)(uintptr_t)p)
                         : Py_XNewRef (Py_None);
      }
    default:
      break;
    }
  PyObject *py = pygi_primitive_storage_to_py (tag, src);
  if (py == NULL)
    {
      if (PyErr_Occurred ())
        PyErr_Clear ();
      PyErr_SetString (PyExc_NotImplementedError, "GArray element type unsupported in to_py");
      return NULL;
    }
  return py;
}

PyObject *
pygi_garray_to_py (GICallableInfo *cb, GITypeInfo *ti, GIArgument *arg, GITransfer transfer)
{
  g_return_val_if_fail (ti != NULL, NULL);
  g_return_val_if_fail (GI_IS_TYPE_INFO (ti), NULL);
  g_return_val_if_fail (arg != NULL, NULL);
  (void)cb;

  GIArrayType array_type = gi_type_info_get_array_type (ti);
  if (array_type == GI_ARRAY_TYPE_BYTE_ARRAY)
    {
      GByteArray *ba = (GByteArray *)arg->v_pointer;
      if (ba == NULL)
        return Py_XNewRef (Py_None);
      PyObject *bytes = PyBytes_FromStringAndSize ((const char *)ba->data, (Py_ssize_t)ba->len);
      if (transfer != GI_TRANSFER_NOTHING)
        g_byte_array_unref (ba);
      return bytes;
    }

  g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (ti, 0);
  if (elem_ti == NULL)
    {
      PyErr_SetString (PyExc_NotImplementedError, "array element type metadata missing");
      return NULL;
    }
  g_autoptr (GIBaseInfo) elem_iface = NULL;
  if (gi_type_info_get_tag (elem_ti) == GI_TYPE_TAG_INTERFACE)
    elem_iface = gi_type_info_get_interface (elem_ti);
  GITypeTag elem_tag = element_storage_tag_for_legacy_to_py (elem_ti, elem_iface);

  PyGIContainerElement element;
  gboolean use_element_plan = pygi_container_element_init (&element, elem_ti) == 0;

  if (array_type == GI_ARRAY_TYPE_PTR_ARRAY)
    {
      GPtrArray *pa = (GPtrArray *)arg->v_pointer;
      if (pa == NULL)
        return Py_XNewRef (Py_None);
      PyObject *list = PyList_New ((Py_ssize_t)pa->len);
      if (list == NULL)
        return NULL;
      for (guint k = 0; k < pa->len; k++)
        {
          PyObject *item = NULL;
          if (use_element_plan && pygi_container_element_can_use_pointer_slot (&element))
            item = pygi_container_element_pointer_to_py (&element, g_ptr_array_index (pa, k));
          else if (elem_tag == GI_TYPE_TAG_INTERFACE && elem_iface != NULL
                   && (GI_IS_STRUCT_INFO (elem_iface) || GI_IS_UNION_INFO (elem_iface)))
            {
              GIArgument elem_arg = { .v_pointer = g_ptr_array_index (pa, k) };
              GITransfer item_transfer = transfer == GI_TRANSFER_EVERYTHING ? GI_TRANSFER_EVERYTHING
                                                                            : GI_TRANSFER_NOTHING;
              item = pygi_argument_to_py_transfer (cb, elem_ti, &elem_arg, item_transfer);
            }
          else
            item = primitive_to_py (elem_tag, &g_ptr_array_index (pa, k));
          if (item == NULL)
            {
              Py_DECREF (list);
              return NULL;
            }
          PyList_SET_ITEM (list, (Py_ssize_t)k, item);
        }
      if (transfer != GI_TRANSFER_NOTHING)
        g_ptr_array_unref (pa);
      return list;
    }

  GArray *ga = (GArray *)arg->v_pointer;
  if (ga == NULL)
    return Py_XNewRef (Py_None);
  gsize elem_size = ga->len > 0 ? g_array_get_element_size (ga) : 0;
  if (elem_size == 0)
    {
      elem_size = use_element_plan ? pygi_container_element_inline_size (&element) : 0;
      if (elem_size == 0)
        elem_size = garray_elem_size (elem_ti, elem_iface);
    }
  PyObject *list = PyList_New ((Py_ssize_t)ga->len);
  if (list == NULL)
    return NULL;
  for (guint k = 0; k < ga->len; k++)
    {
      const char *src = ga->data + (gsize)k * elem_size;
      PyObject *item = use_element_plan ? pygi_container_element_inline_to_py (&element, src)
                                        : primitive_to_py (elem_tag, src);
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)k, item);
    }
  if (transfer != GI_TRANSFER_NOTHING)
    g_array_unref (ga);
  return list;
}
