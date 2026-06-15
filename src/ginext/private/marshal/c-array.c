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

/* c-array.c - IN-side Python sequence -> heap-allocated C array conversion,
 * and OUT-side C array -> Python list/bytes conversion.
 *
 * IN-side dispatches on the element type:
 *   UTF8/FILENAME           -> char *[] (with optional g_strdup per transfer)
 *   GVariant                -> gpointer[] of g_variant_ref_sink()'d nodes
 *   GValue                  -> GValue[] (in-place initialized)
 *   struct/union            -> struct buffer (inline or pointer-array)
 *   object/interface        -> gpointer[] of unwrapped GObject pointers
 *   nested array            -> gchar*** (only outer container; inner strvs leak)
 *   primitives              -> primitive[] via shared element storage */

#include "marshal/c-array.h"
#include "GObject/Boxed.h"
#include "marshal/container-element.h"
#include "marshal/scalar.h"
#include "marshal/string.h"
#include "runtime/type-info.h"
#include "marshal/marshal.h"

#include "marshal/gvalue.h"
#include "GObject/Fundamental.h"
#include "GObject/Object-info.h"
#include "GLib/Variant.h"
#include "common.h"

#include <string.h>

static PyObject *
string_array_item_to_py (const char *s)
{
  if (s == NULL)
    Py_RETURN_NONE;
  PyObject *py = PyUnicode_FromString (s);
  if (py != NULL)
    return py;
  if (!PyErr_ExceptionMatches (PyExc_UnicodeDecodeError))
    return NULL;
  PyErr_Clear ();
  return PyBytes_FromString (s);
}

static void
free_struct_pointer_array_items (gpointer *items, Py_ssize_t n, GType gtype)
{
  for (Py_ssize_t i = 0; i < n; i++)
    {
      gpointer item = items[i];
      if (item != NULL && gtype != G_TYPE_NONE && gtype != 0 && G_TYPE_IS_BOXED (gtype))
        g_boxed_free (gtype, item);
      else
        g_free (item);
    }
}

static void
unref_instantiatable_array_items (gpointer *items, Py_ssize_t n, GType gtype)
{
  for (Py_ssize_t i = 0; i < n; i++)
    {
      if (items[i] != NULL)
        pygi_instantiatable_unref (items[i], gtype);
    }
}

static int
validate_fixed_size (Py_ssize_t n, gsize fixed_size)
{
  if (fixed_size == 0 || n == (Py_ssize_t)fixed_size)
    return 0;
  PyErr_Format (PyExc_ValueError,
                "fixed-size array requires %" G_GSIZE_FORMAT " items, got %zd",
                fixed_size,
                n);
  return -1;
}

static PyObject *
gvalue_array_to_py (GValue *values, gsize n, GITransfer transfer)
{
  PyObject *list = PyList_New ((Py_ssize_t)n);
  if (list == NULL)
    return NULL;
  for (gsize i = 0; i < n; i++)
    {
      PyObject *item = pygi_gvalue_value_to_py (&values[i]);
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)i, item);
    }
  if (transfer != GI_TRANSFER_NOTHING)
    {
      for (gsize i = 0; i < n; i++)
        g_value_unset (&values[i]);
      g_free (values);
    }
  return list;
}

int
pygi_py_to_c_array_invoke (PyObject *h,
                           GITypeInfo *elem_ti,
                           GIArgument *array_arg,
                           GIArgument *len_arg,
                           GITypeInfo *len_ti,
                           gboolean zero_terminated,
                           gsize fixed_size,
                           PyGIArgCleanup *cleanup,
                           GITransfer transfer)
{
  g_return_val_if_fail (elem_ti != NULL, -1);
  g_return_val_if_fail (GI_IS_TYPE_INFO (elem_ti), -1);
  g_return_val_if_fail (array_arg != NULL, -1);
  g_return_val_if_fail (cleanup != NULL, -1);
  GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);

  /* Allow None as a null array. */
  if (h == Py_None)
    {
      array_arg->v_pointer = NULL;
      if (len_ti != NULL)
        gi_argument_set_length (len_ti, 0, len_arg);
      cleanup->kind = PYGI_ARG_CLEANUP_NONE;
      return 0;
    }

  if (elem_tag == GI_TYPE_TAG_VOID)
    {
      /* Opaque gpointer* array: only a boxed pointer wrapper is
       * meaningful; we can't synthesize one from a Python iterable. */
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get ((PyObject *)h, &boxed_ptr) == 0)
        {
          array_arg->v_pointer = boxed_ptr;
          if (len_ti != NULL)
            gi_argument_set_length (len_ti, 0, len_arg);
          cleanup->kind = PYGI_ARG_CLEANUP_NONE;
          return 0;
        }
      PyErr_Clear ();
      PyErr_SetString (PyExc_TypeError,
                       "opaque pointer-array argument accepts only None "
                       "or a boxed pointer wrapper");
      return -1;
    }

  if (elem_tag == GI_TYPE_TAG_UTF8 || elem_tag == GI_TYPE_TAG_FILENAME)
    {
      PyGIContainerElement element;
      if (pygi_container_element_init (&element, elem_ti) != 0 || !element.is_string
          || pygi_container_element_inline_size (&element) != sizeof (gchar *))
        {
          PyErr_SetString (PyExc_NotImplementedError, "string-array element type not supported");
          return -1;
        }
      Py_AUTO_DECREF PyObject *fast
          = PySequence_Fast ((PyObject *)(h), "expected a sequence of strings");
      if (fast == NULL)
        return -1;
      Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);
      char **strv = g_new0 (char *, (gsize)(n + 1));
      if (strv == NULL)
        {
          PyErr_NoMemory ();
          return -1;
        }
      /* Transfer semantics:
         *   NONE: pass borrowed (Python-owned) string pointers; we free only the
         *         container after the call.
         *   CONTAINER: C frees the container; the strings must remain valid for
         *         the duration of the call.  Borrow Python pointers; no cleanup.
         *   EVERYTHING: C frees both container and strings; we must g_strdup so
         *         g_free works.  No cleanup. */
      gboolean dup_strings = (transfer == GI_TRANSFER_EVERYTHING);
      for (Py_ssize_t k = 0; k < n; k++)
        {
          if (pygi_container_element_inline_from_py (&element,
                                                     PySequence_Fast_GET_ITEM (fast, k),
                                                     transfer,
                                                     &strv[k])
              != 0)
            {
              if (dup_strings)
                g_strfreev (strv);
              else
                g_free (strv);
              return -1;
            }
        }
      if (validate_fixed_size (n, fixed_size) != 0)
        {
          if (dup_strings)
            g_strfreev (strv);
          else
            g_free (strv);
          return -1;
        }
      if (len_ti != NULL && gi_argument_set_length (len_ti, n, len_arg) != 0)
        {
          if (dup_strings)
            g_strfreev (strv);
          else
            g_free (strv);
          PyErr_SetString (PyExc_NotImplementedError,
                           "string-array length parameter has unsupported type");
          return -1;
        }
      array_arg->v_pointer = strv;
      if (transfer == GI_TRANSFER_NOTHING)
        {
          cleanup->kind = PYGI_ARG_CLEANUP_FREE; /* free container only */
          cleanup->ptr = strv;
        }
      else
        {
          cleanup->kind = PYGI_ARG_CLEANUP_NONE; /* C owns container */
        }
      return 0;
    }

  /* Enum/flags are always stored as int32 in C arrays. */
  if (gi_type_info_is_enum_or_flags (elem_ti))
    elem_tag = GI_TYPE_TAG_INT32;

  /* Array of structs/unions: each Python instance has primitive fields as
     * Python attributes; copy them into the C struct buffer. Dispatch order:
     * refined cases (GVariant, GValue) first, then generic struct/union, then
     * object/interface. */
  if (elem_tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_ti);
      if (iface != NULL)
        {
          if (gi_type_info_is_variant (elem_ti))
            {
              Py_AUTO_DECREF PyObject *fast
                  = PySequence_Fast ((PyObject *)(h), "expected a sequence");
              if (fast == NULL)
                return -1;
              Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);
              if (validate_fixed_size (n, fixed_size) != 0)
                return -1;
              gpointer *buf = n > 0 ? g_new0 (gpointer, (gsize)n + 1u) : g_new0 (gpointer, 1u);
              if (buf == NULL)
                {
                  PyErr_NoMemory ();
                  return -1;
                }
              for (Py_ssize_t k = 0; k < n; k++)
                {
                  if (pygi_py_item_to_gvariant (PySequence_Fast_GET_ITEM (fast, k), &buf[k]) != 0)
                    {
                      for (Py_ssize_t kk = 0; kk < k; kk++)
                        g_variant_unref ((GVariant *)buf[kk]);
                      g_free (buf);
                      return -1;
                    }
                }
              if (len_ti != NULL && gi_argument_set_length (len_ti, n, len_arg) != 0)
                {
                  for (Py_ssize_t kk = 0; kk < n; kk++)
                    g_variant_unref ((GVariant *)buf[kk]);
                  g_free (buf);
                  PyErr_SetString (PyExc_NotImplementedError,
                                   "variant array length parameter has unsupported type");
                  return -1;
                }
              array_arg->v_pointer = buf;
              cleanup->kind = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_FREE
                                                                : PYGI_ARG_CLEANUP_NONE;
              cleanup->ptr = buf;
              return 0;
            }
          if (gi_type_info_is_gvalue (elem_ti))
            {
              Py_AUTO_DECREF PyObject *fast
                  = PySequence_Fast ((PyObject *)(h), "expected a sequence");
              if (fast == NULL)
                return -1;
              Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);
              if (validate_fixed_size (n, fixed_size) != 0)
                return -1;
              GValue *values = g_new0 (GValue, (gsize)n);
              for (Py_ssize_t k = 0; k < n; k++)
                {
                  PyObject *item = PySequence_Fast_GET_ITEM (fast, k);
                  /* Flat-GValue-array callees (e.g. gvalue_flat_array)
                   * read each slot with g_value_get_int when the
                   * Python source was an int — they CRITICAL on the
                   * silent G_TYPE_INT64 promotion that the generic
                   * pygi_py_to_gvalue_inplace would do for
                   * out-of-int-range values. Range-check here so
                   * pygobject's OverflowError contract is preserved
                   * without breaking the other gvalue paths that rely
                   * on the int->int64 promotion (gvalue_int64_in
                   * etc.). Booleans inherit from PyLong so exclude
                   * them. */
                  if (PyLong_Check (item) && !PyBool_Check (item))
                    {
                      int overflow = 0;
                      long iv = PyLong_AsLongAndOverflow (item, &overflow);
                      if (overflow != 0 || iv > G_MAXINT || iv < G_MININT)
                        {
                          Py_AUTO_DECREF PyObject *repr = PyObject_Str (item);
                          const char *vstr = repr != NULL ? PyUnicode_AsUTF8 (repr) : "?";
                          PyErr_Format (PyExc_OverflowError,
                                        "%s not in range %d to %d",
                                        vstr != NULL ? vstr : "?",
                                        G_MININT,
                                        G_MAXINT);
                          for (Py_ssize_t kk = 0; kk < k; kk++)
                            g_value_unset (&values[kk]);
                          g_free (values);
                          return -1;
                        }
                      if (iv == -1 && PyErr_Occurred ())
                        {
                          for (Py_ssize_t kk = 0; kk < k; kk++)
                            g_value_unset (&values[kk]);
                          g_free (values);
                          return -1;
                        }
                    }
                  PyGIMarshalSlot mslot = {
                    .type = elem_ti,
                    .kind = PYGI_MARSHAL_TARGET_GVALUE,
                    .target.gvalue = &values[k],
                  };
                  if (pygi_marshal_from_py (item, &mslot) != 0)
                    {
                      for (Py_ssize_t kk = 0; kk < k; kk++)
                        g_value_unset (&values[kk]);
                      g_free (values);
                      return -1;
                    }
                }
              if (len_ti != NULL && gi_argument_set_length (len_ti, n, len_arg) != 0)
                {
                  for (Py_ssize_t kk = 0; kk < n; kk++)
                    g_value_unset (&values[kk]);
                  g_free (values);
                  PyErr_SetString (PyExc_NotImplementedError,
                                   "GValue array length parameter has unsupported type");
                  return -1;
                }
              array_arg->v_pointer = values;
              cleanup->kind = PYGI_ARG_CLEANUP_GVALUE_ARRAY;
              cleanup->ptr = values;
              cleanup->n = (gsize)n;
              return 0;
            }
          if (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
            {
              gsize struct_size = gi_struct_or_union_size (iface);
              int is_pointer_array = gi_type_info_is_pointer (elem_ti) || struct_size == 0;
              GType iface_gt = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
              int transfer_full = transfer == GI_TRANSFER_EVERYTHING;
              Py_AUTO_DECREF PyObject *fast
                  = PySequence_Fast ((PyObject *)(h), "expected a sequence");
              if (fast == NULL)
                return -1;
              Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);
              if (validate_fixed_size (n, fixed_size) != 0)
                return -1;

              char *buf;
              if (is_pointer_array)
                {
                  buf = (char *)g_new0 (gpointer, (gsize)n);
                }
              else
                {
                  buf = (char *)g_malloc0 (struct_size * (gsize)n);
                }

              const char *iface_name = gi_base_info_get_name (iface);
              for (Py_ssize_t k = 0; k < n; k++)
                {
                  PyObject *item = PySequence_Fast_GET_ITEM (fast, k);
                  if (is_pointer_array)
                    {
                      gpointer ptr = NULL;
                      if (pygi_boxed_get (item, &ptr) != 0)
                        {
                          if (transfer_full)
                            free_struct_pointer_array_items ((gpointer *)buf, k, iface_gt);
                          g_free (buf);
                          return -1;
                        }
                      if (transfer_full && ptr != NULL)
                        {
                          if (iface_gt != G_TYPE_NONE && iface_gt != 0
                              && G_TYPE_IS_BOXED (iface_gt))
                            ((gpointer *)buf)[k] = g_boxed_copy (iface_gt, ptr);
                          else if (struct_size > 0)
                            ((gpointer *)buf)[k] = g_memdup2 (ptr, struct_size);
                          else
                            {
                              PyErr_SetString (
                                  PyExc_NotImplementedError,
                                  "transfer-full pointer struct array without copy semantics");
                              free_struct_pointer_array_items ((gpointer *)buf, k, iface_gt);
                              g_free (buf);
                              return -1;
                            }
                          if (((gpointer *)buf)[k] == NULL)
                            {
                              free_struct_pointer_array_items ((gpointer *)buf, k, iface_gt);
                              g_free (buf);
                              PyErr_NoMemory ();
                              return -1;
                            }
                        }
                      else
                        {
                          ((gpointer *)buf)[k] = ptr;
                        }
                      continue;
                    }
                  /* Reject non-struct items up front. Without this check,
                   * pygi_struct_info_copy_py_attrs_to_buffer silently
                   * skips fields it can't find on the item and leaves
                   * the struct slot zero-filled — the C callee then
                   * trips an assertion on the unexpected value rather
                   * than surfacing as a TypeError to Python. The Record
                   * builder hangs `gimeta` on every struct/union
                   * class; using its presence as the marker avoids
                   * importing the Python type. */
                  if (!PyObject_HasAttrString (item, "gimeta"))
                    {
                      PyErr_Format (PyExc_TypeError,
                                    "expected %s at array index %zd, got %s",
                                    iface_name != NULL ? iface_name : "struct",
                                    (Py_ssize_t)k,
                                    Py_TYPE (item)->tp_name);
                      if (is_pointer_array)
                        {
                          for (Py_ssize_t kk = 0; kk < k; kk++)
                            g_free (((gpointer *)buf)[kk]);
                        }
                      g_free (buf);
                      return -1;
                    }
                  char *struct_buf;
                  struct_buf = buf + (size_t)k * struct_size;
                  if (pygi_struct_info_copy_py_attrs_to_buffer (item, iface, struct_buf) != 0)
                    {
                      g_free (buf);
                      return -1;
                    }
                }
              if (len_ti != NULL && gi_argument_set_length (len_ti, n, len_arg) != 0)
                {
                  g_free (buf);
                  PyErr_SetString (PyExc_NotImplementedError, "struct array length unsupported");
                  return -1;
                }
              array_arg->v_pointer = buf;
              cleanup->kind = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_FREE
                                                                : PYGI_ARG_CLEANUP_NONE;
              cleanup->ptr = buf;
              return 0;
            }
          if (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface))
            {
              GType iface_gt = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
              int transfer_full = transfer == GI_TRANSFER_EVERYTHING;
              Py_AUTO_DECREF PyObject *fast
                  = PySequence_Fast ((PyObject *)(h), "expected a sequence");
              if (fast == NULL)
                return -1;
              Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);
              if (validate_fixed_size (n, fixed_size) != 0)
                return -1;
              gpointer *buf = n > 0 || zero_terminated
                                  ? g_new0 (gpointer, (gsize)n + (zero_terminated ? 1u : 0u))
                                  : NULL;
              for (Py_ssize_t k = 0; k < n; k++)
                {
                  PyObject *item = PySequence_Fast_GET_ITEM (fast, k);
                  GIArgument tmp = { 0 };
                  PyObject *h_item = (PyObject *)(item);
                  if (pygi_object_info_from_py (h_item, &tmp) != 0)
                    {
                      if (transfer_full)
                        unref_instantiatable_array_items (buf, k, iface_gt);
                      g_free (buf);
                      return -1;
                    }
                  if (transfer_full && tmp.v_pointer != NULL)
                    {
                      gpointer owned = NULL;
                      if (pygi_instantiatable_ref (tmp.v_pointer, iface_gt, &owned) != 0)
                        {
                          unref_instantiatable_array_items (buf, k, iface_gt);
                          g_free (buf);
                          return -1;
                        }
                      buf[k] = owned;
                    }
                  else
                    {
                      buf[k] = tmp.v_pointer;
                    }
                }
              if (len_ti != NULL && gi_argument_set_length (len_ti, n, len_arg) != 0)
                {
                  if (transfer_full)
                    unref_instantiatable_array_items (buf, n, iface_gt);
                  g_free (buf);
                  PyErr_SetString (PyExc_NotImplementedError, "object array length unsupported");
                  return -1;
                }
              array_arg->v_pointer = buf;
              cleanup->kind = (transfer == GI_TRANSFER_NOTHING) ? PYGI_ARG_CLEANUP_FREE
                                                                : PYGI_ARG_CLEANUP_NONE;
              cleanup->ptr = buf;
              return 0;
            }
        }
    }

  /* Array of arrays (e.g. GStrv elements): each outer element is gchar**. */
  if (elem_tag == GI_TYPE_TAG_ARRAY)
    {
      g_autoptr (GITypeInfo) inner_ti = gi_type_info_get_param_type (elem_ti, 0);
      if (inner_ti == NULL)
        {
          PyErr_SetString (PyExc_NotImplementedError, "nested array element type metadata missing");
          return -1;
        }
      GITypeTag inner_tag = gi_type_info_get_tag (inner_ti);
      if (inner_tag != GI_TYPE_TAG_UTF8 && inner_tag != GI_TYPE_TAG_FILENAME)
        {
          PyErr_SetString (PyExc_NotImplementedError, "nested array inner type not utf8");
          return -1;
        }
      Py_AUTO_DECREF PyObject *fast_outer
          = PySequence_Fast ((PyObject *)(h), "expected a sequence");
      if (fast_outer == NULL)
        return -1;
      Py_ssize_t no = PySequence_Fast_GET_SIZE (fast_outer);
      if (validate_fixed_size (no, fixed_size) != 0)
        return -1;
      /* Allocate one extra slot for a NULL terminator (zero-terminated arrays). */
      gchar ***buf = g_new0 (gchar **, (gsize)(no + 1));
      for (Py_ssize_t k = 0; k < no; k++)
        {
          PyObject *fast_inner = PySequence_Fast (PySequence_Fast_GET_ITEM (fast_outer, k),
                                                  "expected sequence of strings");
          if (fast_inner == NULL)
            {
              for (Py_ssize_t kk = 0; kk < k; kk++)
                g_strfreev (buf[kk]);
              g_free (buf);
              return -1;
            }
          Py_ssize_t ni = PySequence_Fast_GET_SIZE (fast_inner);
          gchar **strv2 = g_new0 (gchar *, (gsize)(ni + 1));
          for (Py_ssize_t m = 0; m < ni; m++)
            {
              const char *s = PyUnicode_AsUTF8 (PySequence_Fast_GET_ITEM (fast_inner, m));
              if (s == NULL)
                {
                  g_strfreev (strv2);
                  Py_DECREF (fast_inner);
                  for (Py_ssize_t kk = 0; kk < k; kk++)
                    g_strfreev (buf[kk]);
                  g_free (buf);
                  return -1;
                }
              strv2[m] = g_strdup (s);
            }
          Py_DECREF (fast_inner);
          buf[k] = strv2;
        }
      if (len_ti != NULL && gi_argument_set_length (len_ti, no, len_arg) != 0)
        {
          for (Py_ssize_t kk = 0; kk < no; kk++)
            g_strfreev (buf[kk]);
          g_free (buf);
          PyErr_SetString (PyExc_NotImplementedError, "nested array length unsupported");
          return -1;
        }
      array_arg->v_pointer = buf;
      /* For TRANSFER_NOTHING we should free the outer container; inner strvs
         * leak (acceptable for now).  For CONTAINER/EVERYTHING C handles. */
      if (transfer == GI_TRANSFER_NOTHING)
        {
          cleanup->kind = PYGI_ARG_CLEANUP_FREE;
          cleanup->ptr = buf;
        }
      else
        {
          cleanup->kind = PYGI_ARG_CLEANUP_NONE;
        }
      return 0;
    }

  PyGIContainerElement element;
  if (pygi_container_element_init (&element, elem_ti) != 0)
    {
      PyErr_Format (PyExc_NotImplementedError,
                    "GI argument conversion not implemented for array element type: %s",
                    gi_type_tag_to_string (elem_tag));
      return -1;
    }
  gsize elem_size = pygi_container_element_inline_size (&element);
  if (elem_size == 0)
    {
      PyErr_Format (PyExc_NotImplementedError,
                    "GI argument conversion not implemented for array element type: %s",
                    gi_type_tag_to_string (elem_tag));
      return -1;
    }


  /* Bulk-copy fast path: a contiguous buffer (bytes/bytearray/memoryview/numpy
   * array) of fixed-width POD scalar elements is memcpy'd in one shot instead
   * of converting one Python int per element. Runs BEFORE PySequence_Fast()
   * (which would itself materialize n Python ints). ~20 MB/s -> ~GB/s; anything
   * without a matching C-contiguous buffer falls through to the generic loop. */
  {
    gboolean pod_scalar = (elem_tag == GI_TYPE_TAG_INT8 || elem_tag == GI_TYPE_TAG_UINT8
                           || elem_tag == GI_TYPE_TAG_INT16 || elem_tag == GI_TYPE_TAG_UINT16
                           || elem_tag == GI_TYPE_TAG_INT32 || elem_tag == GI_TYPE_TAG_UINT32
                           || elem_tag == GI_TYPE_TAG_INT64 || elem_tag == GI_TYPE_TAG_UINT64
                           || elem_tag == GI_TYPE_TAG_FLOAT || elem_tag == GI_TYPE_TAG_DOUBLE);
    if (pod_scalar && !gi_type_info_is_pointer (elem_ti) && PyObject_CheckBuffer ((PyObject *)h))
      {
        Py_buffer view;
        if (PyObject_GetBuffer ((PyObject *)h, &view, PyBUF_C_CONTIGUOUS) == 0)
          {
            gboolean item_ok = (view.itemsize == (Py_ssize_t)elem_size || view.itemsize == 1);
            if (item_ok && view.len >= 0 && (gsize)view.len % elem_size == 0)
              {
                Py_ssize_t bn = (Py_ssize_t)((gsize)view.len / elem_size);
                if (validate_fixed_size (bn, fixed_size) != 0)
                  {
                    PyBuffer_Release (&view);
                    return -1;
                  }
                gsize balloc = (gsize)bn + (zero_terminated ? 1u : 0u);
                void *bbuf = balloc > 0 ? g_malloc0 (elem_size * balloc) : NULL;
                if (balloc > 0 && bbuf == NULL)
                  {
                    PyBuffer_Release (&view);
                    PyErr_NoMemory ();
                    return -1;
                  }
                if (view.len > 0)
                  memcpy (bbuf, view.buf, (size_t)view.len);
                PyBuffer_Release (&view);
                if (len_ti != NULL && gi_argument_set_length (len_ti, bn, len_arg) != 0)
                  {
                    g_free (bbuf);
                    PyErr_SetString (PyExc_NotImplementedError,
                                     "array length parameter has unsupported integer type");
                    return -1;
                  }
                array_arg->v_pointer = bbuf;
                if (transfer == GI_TRANSFER_NOTHING)
                  {
                    cleanup->kind = PYGI_ARG_CLEANUP_FREE;
                    cleanup->ptr = bbuf;
                  }
                else
                  {
                    cleanup->kind = PYGI_ARG_CLEANUP_NONE;
                  }
                return 0;
              }
            PyBuffer_Release (&view);
          }
        else
          {
            PyErr_Clear ();
          }
      }
  }

  Py_AUTO_DECREF PyObject *fast = PySequence_Fast ((PyObject *)(h), "expected a sequence");
  if (fast == NULL)
    return -1;
  Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);
  if (validate_fixed_size (n, fixed_size) != 0)
    return -1;
  gsize alloc_n = (gsize)n + (zero_terminated ? 1u : 0u);
  void *buf = alloc_n > 0 ? g_malloc0 (elem_size * alloc_n) : NULL;
  if (alloc_n > 0 && buf == NULL)
    {
      PyErr_NoMemory ();
      return -1;
    }

  for (Py_ssize_t k = 0; k < n; k++)
    {
      if (pygi_container_element_inline_from_py (&element,
                                                 PySequence_Fast_GET_ITEM (fast, k),
                                                 transfer,
                                                 (char *)buf + (size_t)k * elem_size)
          != 0)
        {
          g_free (buf);
          return -1;
        }
    }

  if (len_ti != NULL && gi_argument_set_length (len_ti, n, len_arg) != 0)
    {
      g_free (buf);
      PyErr_SetString (PyExc_NotImplementedError,
                       "array length parameter has unsupported integer type");
      return -1;
    }

  array_arg->v_pointer = buf;
  /* For non-string element types: TRANSFER_EVERYTHING/CONTAINER mean C frees
     * the buffer; we don't.  TRANSFER_NOTHING means we free. */
  if (transfer == GI_TRANSFER_NOTHING)
    {
      cleanup->kind = PYGI_ARG_CLEANUP_FREE;
      cleanup->ptr = buf;
    }
  else
    {
      cleanup->kind = PYGI_ARG_CLEANUP_NONE;
    }
  return 0;
}

PyObject *
pygi_c_array_to_py (GICallableInfo *cb,
                    GITypeInfo *ti,
                    GIArgument *arg,
                    GITypeInfo *len_ti,
                    GIArgument *len_arg,
                    GITransfer transfer)
{
  g_return_val_if_fail (cb != NULL, NULL);
  g_return_val_if_fail (GI_IS_CALLABLE_INFO (cb), NULL);
  g_return_val_if_fail (ti != NULL, NULL);
  g_return_val_if_fail (GI_IS_TYPE_INFO (ti), NULL);
  g_return_val_if_fail (arg != NULL, NULL);
  g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (ti, 0);
  gsize len = 0;
  if (elem_ti == NULL)
    {
      pygi_set_unimplemented_type_error ("GI return conversion",
                                         ti,
                                         "array element type metadata missing");
      return NULL;
    }
  if (len_ti != NULL && len_arg != NULL)
    {
      if (gi_argument_get_length (len_ti, len_arg, &len) != 0)
        {
          pygi_set_unimplemented_type_error ("GI return conversion", len_ti, "array length type");
          return NULL;
        }
    }
  else if (gi_type_info_get_array_fixed_size (ti, &len))
    {
    }
  else if (gi_type_info_is_zero_terminated (ti))
    {
      if (arg->v_pointer == NULL)
        len = 0;
      else
        {
          GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);
          if (elem_tag == GI_TYPE_TAG_UTF8 || elem_tag == GI_TYPE_TAG_FILENAME)
            {
              gchar **strv = (gchar **)arg->v_pointer;
              while (strv[len] != NULL)
                len++;
            }
          else if (elem_tag == GI_TYPE_TAG_UNICHAR)
            {
              gunichar *chars = (gunichar *)arg->v_pointer;
              while (chars[len] != 0)
                len++;
            }
          else if (elem_tag == GI_TYPE_TAG_ARRAY)
            {
              gpointer *items = (gpointer *)arg->v_pointer;
              while (items[len] != NULL)
                len++;
            }
          else if (gi_type_info_is_gvalue (elem_ti))
            {
              GValue *values = (GValue *)arg->v_pointer;
              while (G_VALUE_TYPE (&values[len]) != 0)
                len++;
            }
          else if (elem_tag == GI_TYPE_TAG_INTERFACE && gi_type_info_is_pointer (elem_ti))
            {
              gpointer *items = (gpointer *)arg->v_pointer;
              while (items[len] != NULL)
                len++;
            }
          else
            {
              gsize elem_size = gi_type_info_array_element_size (elem_ti);
              if (elem_size == 0)
                {
                  pygi_set_unimplemented_type_error ("GI return conversion",
                                                     ti,
                                                     "zero-terminated C array element type");
                  return NULL;
                }
              const char *base = (const char *)arg->v_pointer;
              while (TRUE)
                {
                  gboolean is_zero = TRUE;
                  for (gsize b = 0; b < elem_size; b++)
                    {
                      if (base[len * elem_size + b] != 0)
                        {
                          is_zero = FALSE;
                          break;
                        }
                    }
                  if (is_zero)
                    break;
                  len++;
                }
            }
        }
    }
  else
    {
      pygi_set_unimplemented_type_error ("GI return conversion", ti, "array length missing");
      return NULL;
    }
  if (arg->v_pointer == NULL)
    return PyList_New (0);

  if (gi_type_info_is_gvalue (elem_ti))
    return gvalue_array_to_py ((GValue *)arg->v_pointer, len, transfer);

  gsize elem_size = gi_type_info_array_element_size (elem_ti);
  if (elem_size == 0)
    {
      pygi_set_unimplemented_type_error ("GI return conversion", elem_ti, "C array element type");
      return NULL;
    }

  /* uint8 arrays -> bytes, not list */
  GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);
  if (elem_tag == GI_TYPE_TAG_UINT8)
    {
      PyObject *b = PyBytes_FromStringAndSize ((const char *)arg->v_pointer, (Py_ssize_t)len);
      if (transfer == GI_TRANSFER_EVERYTHING)
        g_free (arg->v_pointer);
      return (PyObject *)(b);
    }

  PyObject *list = PyList_New ((Py_ssize_t)len);
  if (list == NULL)
    return NULL;
  const char *base = (const char *)arg->v_pointer;
  GITypeTag elem_tag2 = gi_type_info_get_tag (elem_ti);
  PyGIContainerElement element;
  gboolean use_element_plan = pygi_container_element_init (&element, elem_ti) == 0;
  for (gsize i = 0; i < len; i++)
    {
      PyObject *item;
      if (elem_tag2 == GI_TYPE_TAG_ARRAY)
        {
          gchar **strv = *(gchar ***)((void *)(base + i * elem_size));
          item = pygi_strv_to_py_list (strv, GI_TRANSFER_NOTHING);
        }
      else if (elem_tag2 == GI_TYPE_TAG_UNICHAR)
        {
          item = PyUnicode_FromOrdinal ((int)*(const gunichar *)(base + i * elem_size));
        }
      else if (elem_tag2 == GI_TYPE_TAG_UTF8 || elem_tag2 == GI_TYPE_TAG_FILENAME)
        {
          item = string_array_item_to_py (*(char *const *)(base + i * elem_size));
        }
      else if (use_element_plan)
        {
          item = pygi_container_element_inline_to_py (&element, base + i * elem_size);
        }
      else
        {
          GIArgument elem_arg = { 0 };
          if (pygi_load_array_element (elem_ti, base, (guint)i, elem_size, &elem_arg) != 0)
            {
              Py_DECREF (list);
              pygi_set_unimplemented_type_error ("GI return conversion",
                                                 elem_ti,
                                                 "C array element conversion");
              return NULL;
            }
          /* Only a transfer-everything array hands ownership of its elements
           * to the caller; a transfer-container array (e.g. the GParamSpec*[]
           * from g_object_class_list_properties) owns just the outer block,
           * its elements stay borrowed. Passing the array transfer straight
           * through would make interface_to_py unref a borrowed element (a
           * GParamSpec double-unref → crash on the next call). */
          GITransfer elem_transfer
              = (transfer == GI_TRANSFER_EVERYTHING) ? GI_TRANSFER_EVERYTHING : GI_TRANSFER_NOTHING;
          item = pygi_argument_to_py_transfer (cb, elem_ti, &elem_arg, elem_transfer);
        }
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, (Py_ssize_t)i, (PyObject *)(item));
    }
  /* Free the outer block for both transfer-everything and transfer-container
   * (the caller owns the block in both cases). */
  if (transfer != GI_TRANSFER_NOTHING)
    g_free (arg->v_pointer);
  return (PyObject *)(list);
}
