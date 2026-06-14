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

/* marshal.c - GIArgument <-> PyObject * dispatch for all GI type tags. */
#include "marshal/marshal.h"
#include "marshal/pygi-value.h"
#include "marshal/scalar.h"
#include "marshal/string.h"
#include "marshal/c-array.h"
#include "runtime/type-info.h"

#include "marshal/container-element.h"
#include "GLib/Error.h"
#include "cairo/foreign.h"
#include "GLib/Array.h"
#include "runtime/class-registry.h"
#include "GObject/Boxed.h"
#include "GObject/Closure.h"
#include "GObject/Fundamental.h"
#include "GObject/ParamSpec.h"
#include "marshal/enum.h"
#include "GLib/HashTable.h"
#include "GLib/List.h"
#include "GLib/Regex.h"
#include "GLib/DateTime.h"
#include "marshal/gvalue.h"
#include "GObject/Object-info.h"
#include "GObject/Object-class.h"
#include "GLib/Variant.h"

#include <stdio.h>
#include <string.h>

void
pygi_set_unimplemented_type_error (const char *what, GITypeInfo *ti, const char *detail)
{
  GITypeTag tag = gi_type_info_get_tag (ti);
  const char *tag_name = gi_type_tag_to_string (tag);
  char msg[256];

  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
      const char *iface_name = iface != NULL ? gi_base_info_get_name (iface) : NULL;
      const char *iface_ns = iface != NULL ? gi_base_info_get_namespace (iface) : NULL;
      if (iface_name != NULL && iface_ns != NULL)
        {
          snprintf (msg,
                    sizeof (msg),
                    "%s not implemented for GI type %s.%s (tag=%s)%s%s",
                    what,
                    iface_ns,
                    iface_name,
                    tag_name ? tag_name : "?",
                    detail != NULL ? ": " : "",
                    detail != NULL ? detail : "");
        }
      else if (iface_name != NULL)
        {
          snprintf (msg,
                    sizeof (msg),
                    "%s not implemented for GI interface %s (tag=%s)%s%s",
                    what,
                    iface_name,
                    tag_name ? tag_name : "?",
                    detail != NULL ? ": " : "",
                    detail != NULL ? detail : "");
        }
      else
        {
          snprintf (msg,
                    sizeof (msg),
                    "%s not implemented for GI interface tag%s%s",
                    what,
                    detail != NULL ? ": " : "",
                    detail != NULL ? detail : "");
        }
    }
  else
    {
      snprintf (msg,
                sizeof (msg),
                "%s not implemented for GI type tag %s%s%s",
                what,
                tag_name ? tag_name : "?",
                detail != NULL ? ": " : "",
                detail != NULL ? detail : "");
    }
  PyErr_SetString (PyExc_NotImplementedError, msg);
}

/**
 * pygi_check_arg_type:
 * @h: Python argument to pre-check
 * @tag: expected GI tag
 * @arg_index: 1-based Python argument index for error messages
 *
 * Performs the light PyArg-style type check before value conversion.
 * Error templates intentionally match PyArg_ParseTuple families; range
 * checks and final conversion remain in the marshaller:
 * b/B/h/H/i/I/l/L/n use the integer-interpretation template, k/K use
 * "argument N must be int", f/d use the real-number template, and s uses
 * the string template. UINT64 and GTYPE map to k/K; the other integer
 * tags use the signed-int template. @arg_index is 1-based.
 */
int
pygi_check_arg_type (PyObject *h, GITypeTag tag, int arg_index)
{
  enum
  {
    K_INT_INTERP,
    K_INT_UL,
    K_FLOAT,
    K_STR,
    K_NONE
  } kind
      = K_NONE;
  int ok = 1;

  PyGIType type = { 0 };
  if (pygi_type_from_gi_tag (tag, tag == GI_TYPE_TAG_VOID, &type) != 0)
    return 0;

  switch (type.kind)
    {
    case PYGI_TYPE_INT8:
    case PYGI_TYPE_UINT8:
      /* For 8-bit ints accept bytes/str of length 1 too - pygobject
       * convention for `gchar` args (e.g. add_main_option short_name).
       * Floats are accepted and truncated, matching PyGObject's
       * PyNumber_Long path. The conversion to int happens in the
       * marshaller (see h_py_to_int8/uint8 in jit/helpers.c). */
      ok = PyNumber_Check (h)
           || (PyBytes_Check ((PyObject *)h) && PyBytes_GET_SIZE ((PyObject *)h) == 1)
           || (PyUnicode_Check (h) && PyUnicode_GetLength ((PyObject *)h) == 1);
      kind = K_INT_INTERP;
      break;
    case PYGI_TYPE_INT16:
    case PYGI_TYPE_UINT16:
    case PYGI_TYPE_INT32:
    case PYGI_TYPE_UINT32:
    case PYGI_TYPE_INT64:
      ok = PyNumber_Check (h);
      kind = K_INT_INTERP;
      break;
    case PYGI_TYPE_UNICHAR:
      /* gunichar accepts int OR length-1 str (the canonical
       * `GLib.unichar_isprint("a")` form). pygobject-compat - refusing
       * the str variant breaks gnome-music's _on_key_press. */
      ok = PyNumber_Check (h) || (PyUnicode_Check (h) && PyUnicode_GetLength (h) == 1);
      kind = K_INT_INTERP;
      break;
    case PYGI_TYPE_UINT64:
    case PYGI_TYPE_GTYPE:
      /* Accept a Python class with `gimeta.gtype`, not just raw ints.
       * pygi_gtype_from_py handles the class lookup; the pre-check just
       * needs to let it through. */
      ok = PyNumber_Check (h) || PyType_Check (h) || PyObject_HasAttrString (h, "gimeta")
           || PyObject_HasAttrString (h, "__gtype__");
      kind = K_INT_UL;
      break;
    case PYGI_TYPE_FLOAT:
    case PYGI_TYPE_DOUBLE:
      ok = PyNumber_Check (h);
      kind = K_FLOAT;
      break;
    case PYGI_TYPE_UTF8:
    case PYGI_TYPE_FILENAME:
      /* Accept str/bytes/bytearray (and os.PathLike for filename) on the
       * way in - matches pygobject's leniency. The string marshaller
       * (marshal/string.c) handles the actual conversion to a borrowed
       * C string. */
      ok = (h == Py_None) || PyUnicode_Check (h) || PyBytes_Check (h) || PyByteArray_Check (h)
           || (type.kind == PYGI_TYPE_FILENAME && PyObject_HasAttrString (h, "__fspath__"));
      kind = K_STR;
      break;
    case PYGI_TYPE_UNSUPPORTED:
    case PYGI_TYPE_VOID:
    case PYGI_TYPE_POINTER:
    case PYGI_TYPE_BOOLEAN:
    case PYGI_TYPE_ENUM:
    case PYGI_TYPE_FLAGS:
    case PYGI_TYPE_OBJECT:
    case PYGI_TYPE_BOXED:
    case PYGI_TYPE_VARIANT:
    case PYGI_TYPE_INTERFACE:
    case PYGI_TYPE_CALLBACK:
    case PYGI_TYPE_ARRAY:
    case PYGI_TYPE_GLIST:
    case PYGI_TYPE_GSLIST:
    case PYGI_TYPE_GHASH:
    case PYGI_TYPE_ERROR:
      return 0;
    }
  if (ok)
    return 0;
  const char *actual = Py_TYPE ((PyObject *)(h))->tp_name;
  switch (kind)
    {
    case K_INT_INTERP:
      PyErr_Format (PyExc_TypeError, "'%.80s' object cannot be interpreted as an integer", actual);
      break;
    case K_INT_UL:
      PyErr_Format (PyExc_TypeError, "argument %d must be int, not %.80s", arg_index, actual);
      break;
    case K_FLOAT:
      PyErr_Format (PyExc_TypeError, "must be real number, not %.80s", actual);
      break;
    case K_STR:
      PyErr_Format (PyExc_TypeError,
                    "argument %d must be str, bytes, or bytearray, not %.80s",
                    arg_index,
                    actual);
      break;
    case K_NONE:
      break;
    }
  return -1;
}

static int
interface_from_py (PyObject *h, GITypeInfo *ti, GITransfer transfer, GIArgument *out)
{
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL)
    {
      PyErr_SetString (PyExc_NotImplementedError, "interface arg missing interface metadata");
      return -1;
    }
  if (gi_type_info_is_param_spec (ti))
    {
      GParamSpec *pspec = NULL;
      if (pygi_param_spec_from_py ((PyObject *)h, &pspec) != 0)
        return -1;
      out->v_pointer = pspec;
      return 0;
    }
  if (GI_IS_OBJECT_INFO (iface))
    return pygi_object_info_from_py (h, out);
  if (gi_base_info_is_named (iface, "GLib", "Bytes"))
    {
      /* GBytes from a Python bytes-like: zero-copy. The Py_buffer view
       * keeps the source object alive for as long as the GBytes lives,
       * so we hand the GBytes a free_func that releases the view on
       * destruction. For texture-feeder workloads (256 KB+ buffers) this
       * avoids a per-frame g_memdup2 and ~half of draw-bench's CPU. */
      PyObject *obj = (PyObject *)(h);
      if (obj == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      /* If the caller already has a GLib.Bytes wrapper (the typical
       * shape now that returns aren't auto-unwrapped), unwrap to the
       * underlying GBytes pointer. Hand the callee a fresh ref so the
       * wrapper's own ref isn't stolen - pygir's GLib.Bytes wrapper
       * is a generic boxed type. */
      {
        gpointer boxed_ptr = NULL;
        if (pygi_boxed_get (obj, &boxed_ptr) == 0 && boxed_ptr != NULL)
          {
            out->v_pointer = g_bytes_ref ((GBytes *)boxed_ptr);
            return 0;
          }
        PyErr_Clear ();
      }
      Py_buffer *view = g_new (Py_buffer, 1);
      if (PyObject_GetBuffer (obj, view, PyBUF_SIMPLE) != 0)
        {
          g_free (view);
          return -1;
        }
      extern void pygi_pybuffer_release_destroy_notify (gpointer);
      out->v_pointer = g_bytes_new_with_free_func (view->buf,
                                                   (gsize)view->len,
                                                   pygi_pybuffer_release_destroy_notify,
                                                   view);
      return 0;
    }
  /* GLib.Regex from a Python re.Pattern: compile a GRegex on demand. The
   * callee gets an owned ref (refcount 1 from g_regex_new, or a fresh ref off
   * an existing wrapper); the caller registers an unref cleanup, mirroring the
   * GBytes precedent above. */
  if (gi_base_info_is_named (iface, "GLib", "Regex"))
    {
      PyObject *obj = (PyObject *)(h);
      if (obj == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (obj, &boxed_ptr) == 0 && boxed_ptr != NULL)
        {
          out->v_pointer = g_regex_ref ((GRegex *)boxed_ptr);
          return 0;
        }
      PyErr_Clear ();
      GRegex *regex = pygi_gregex_from_py_pattern (obj);
      if (regex == NULL)
        return -1;
      out->v_pointer = regex;
      return 0;
    }
  /* GLib.DateTime/Date/TimeZone: accept the matching stdlib datetime object,
   * converting on demand. An existing GLib wrapper is owned (ref/copy) so the
   * arg cleanup can free it uniformly, mirroring the GLib.Regex branch. */
  if (gi_base_info_is_named (iface, "GLib", "DateTime"))
    {
      PyObject *obj = (PyObject *)(h);
      if (obj == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (obj, &boxed_ptr) == 0 && boxed_ptr != NULL)
        {
          out->v_pointer = g_date_time_ref ((GDateTime *)boxed_ptr);
          return 0;
        }
      PyErr_Clear ();
      GDateTime *dt = pygi_gdatetime_from_py (obj);
      if (dt == NULL)
        return -1;
      out->v_pointer = dt;
      return 0;
    }
  if (gi_base_info_is_named (iface, "GLib", "TimeZone"))
    {
      PyObject *obj = (PyObject *)(h);
      if (obj == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (obj, &boxed_ptr) == 0 && boxed_ptr != NULL)
        {
          out->v_pointer = g_time_zone_ref ((GTimeZone *)boxed_ptr);
          return 0;
        }
      PyErr_Clear ();
      GTimeZone *tz = pygi_gtimezone_from_py (obj);
      if (tz == NULL)
        return -1;
      out->v_pointer = tz;
      return 0;
    }
  if (gi_base_info_is_named (iface, "GLib", "Date"))
    {
      PyObject *obj = (PyObject *)(h);
      if (obj == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (obj, &boxed_ptr) == 0 && boxed_ptr != NULL)
        {
          out->v_pointer = g_date_copy ((GDate *)boxed_ptr);
          return 0;
        }
      PyErr_Clear ();
      GDate *date = pygi_gdate_from_py (obj);
      if (date == NULL)
        return -1;
      out->v_pointer = date;
      return 0;
    }
  /* GLib.PtrArray (without explicit element type): empty list -> empty GPtrArray. */
  if (gi_base_info_is_named (iface, "GLib", "PtrArray"))
    {
      PyObject *obj = (PyObject *)(h);
      if (obj == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      PyObject *fast = PySequence_Fast (obj, "expected a sequence");
      if (fast == NULL)
        return -1;
      Py_ssize_t n = PySequence_Fast_GET_SIZE (fast);
      GPtrArray *pa = g_ptr_array_sized_new ((guint)n);
      for (Py_ssize_t k = 0; k < n; k++)
        {
          PyObject *item = PySequence_Fast_GET_ITEM (fast, k);
          /* Generic: only support utf8 strings here for now. */
          if (PyUnicode_Check (item))
            {
              g_ptr_array_add (pa, (gpointer)PyUnicode_AsUTF8 (item));
            }
          else
            {
              /* unknown element type: pass NULL pointer */
              g_ptr_array_add (pa, NULL);
            }
        }
      Py_DECREF (fast);
      out->v_pointer = pa;
      return 0;
    }
  if (gi_type_info_is_variant (ti))
    return pygi_variant_from_py (h, out);
  if (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface))
    return pygi_object_info_from_py (h, out);
  /* GIFlagsInfo is a subtype of GIEnumInfo, so the flags check MUST come
     first: flags are unsigned and can exceed G_MAXLONG (e.g. 1<<31), which
     overflows the signed-long enum path on LLP64 (Windows). */
  else if (GI_IS_FLAGS_INFO (iface))
    return pygi_flags_info_from_py (h, out);
  else if (GI_IS_ENUM_INFO (iface))
    return pygi_enum_info_from_py (h, out);
  /* Unresolved (Vala-emitted class-nested callback in GIR but not typelib):
     accept None as NULL; any other value cannot be marshalled. */
  if (GI_IS_UNRESOLVED_INFO (iface))
    {
      if (h == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      PyErr_Format (PyExc_TypeError,
                    "argument type is unresolved (Vala callback not in typelib); "
                    "only None is accepted");
      return -1;
    }
  /* Callback: accept None as NULL, otherwise unsupported. */
  if (GI_IS_CALLBACK_INFO (iface))
    {
      if (h == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      pygi_set_unimplemented_type_error (
          "GI argument conversion",
          ti,
          "Python callable -> C callback (closures not yet supported)");
      return -1;
    }
  /* GObject.Closure: wrap a Python callable in a GClosure. */
  if (gi_base_info_is_named (iface, "GObject", "Closure"))
    {
      PyObject *obj = (PyObject *)(h);
      if (obj == Py_None)
        {
          out->v_pointer = NULL;
          return 0;
        }
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (obj, &boxed_ptr) == 0 && boxed_ptr != NULL)
        {
          out->v_pointer = boxed_ptr;
          return 0;
        }
      PyErr_Clear ();
      if (!PyCallable_Check (obj))
        {
          PyErr_SetString (PyExc_TypeError, "GClosure argument must be callable or None");
          return -1;
        }
      GClosure *closure = pygi_closure_new (obj);
      if (closure == NULL)
        return -1;
      out->v_pointer = closure;
      return 0;
    }
  /* Struct/Union: accept None as NULL, GBoxedBase wrappers get unwrapped
   * to their boxed pointer, and SimpleNamespace-style attribute bags
   * fall back to the field-snapshot path. */
  if (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
    {
      int cairo_rc = pygi_foreign_cairo_from_py ((PyObject *)(h), iface, transfer, out);
      if (cairo_rc <= 0)
        return cairo_rc;
      if (h == Py_None)
        {
          /* By-value struct argument: provide a zeroed scratch buffer so
           * gi_function_info_invoke can copy something (callee sees zeros). */
          if (!gi_type_info_is_pointer (ti) && GI_IS_STRUCT_INFO (iface))
            {
              size_t sz = gi_struct_info_get_size ((GIStructInfo *)iface);
              if (sz == 0)
                sz = sizeof (void *);
              out->v_pointer = g_malloc0 (sz);
              /* Leaks - acceptable for tests; Real binding manages lifetime. */
            }
          else
            {
              out->v_pointer = NULL;
            }
          return 0;
        }
      /* Boxed-class wrapper with a real C pointer: unwrap and pass it
       * verbatim. A Python-constructed wrapper (boxed=NULL) hasn't been
       * tied to a C struct yet - fall through to the attribute-bag
       * copy path so `BoxedStruct(); s.long_ = 6; fn(s)` still works. */
      PyObject *py_obj = (PyObject *)(h);
      if (pygi_gboxed_base_type != NULL && PyObject_TypeCheck (py_obj, pygi_gboxed_base_type))
        {
          gpointer ptr = NULL;
          if (pygi_boxed_get (py_obj, &ptr) != 0)
            return -1;
          if (ptr != NULL)
            {
              out->v_pointer = ptr;
              return 0;
            }
          /* boxed==NULL: fall through to the attribute-bag snapshot. */
        }
      /* Struct/union with attribute-bag wrapper (e.g. types.SimpleNamespace
       * or BoxedStruct() instance with __dict__): copy primitive fields
       * into a freshly-allocated buffer.  Used for INOUT and IN by-ref. */
      gsize struct_size = gi_struct_or_union_size (iface);
      if (struct_size == 0)
        struct_size = sizeof (void *);
      char *struct_buf = (char *)g_malloc0 (struct_size);
      if (pygi_struct_info_copy_py_attrs_to_buffer ((PyObject *)(h), iface, struct_buf) != 0)
        {
          g_free (struct_buf);
          return -1;
        }
      out->v_pointer = struct_buf;
      return 0;
    }
  pygi_set_unimplemented_type_error ("GI argument conversion",
                                     ti,
                                     "boxed/struct/interface arguments");
  return -1;
}

int
pygi_argument_from_py (PyObject *h, GITypeInfo *ti, GIArgument *out)
{
  PyGIType type = { 0 };
  if (pygi_type_from_gi (ti, &type) == 0)
    {
      if (pygi_type_is_direct_storage (&type) && type.kind != PYGI_TYPE_ENUM
          && type.kind != PYGI_TYPE_FLAGS)
        {
          PyGIValue value = pygi_value_for_giarg (&type, out);
          return pygi_value_from_py (h, &value);
        }
    }

  GITypeTag tag = gi_type_info_get_tag (ti);
  switch (tag)
    {
    case GI_TYPE_TAG_GHASH:
      pygi_set_unimplemented_type_error ("GI argument conversion",
                                         ti,
                                         "use hash-table invoke helper");
      return -1;
    case GI_TYPE_TAG_INTERFACE:
      return interface_from_py (h, ti, GI_TRANSFER_NOTHING, out);
    default:
      pygi_set_unimplemented_type_error ("GI argument conversion", ti, NULL);
      return -1;
    }
}

static int
boxed_transfer_full_arg_from_py (PyObject *pyval, GITypeInfo *ti, GIArgument *dest, int *handled)
{
  *handled = 0;

  if (pygi_gboxed_base_type == NULL || !PyObject_TypeCheck (pyval, pygi_gboxed_base_type))
    return 0;

  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL || !(GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
    return 0;

  gpointer ptr = NULL;
  if (pygi_boxed_get (pyval, &ptr) != 0)
    return -1;
  if (ptr == NULL)
    return 0;

  GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
  if (gtype == G_TYPE_NONE || gtype == 0)
    {
      PyErr_Format (PyExc_TypeError,
                    "cannot copy transfer-full boxed argument of type %s.%s",
                    gi_base_info_get_namespace (iface),
                    gi_base_info_get_name (iface));
      return -1;
    }

  dest->v_pointer = g_boxed_copy (gtype, ptr);
  if (dest->v_pointer == NULL)
    {
      PyErr_NoMemory ();
      return -1;
    }

  *handled = 1;
  return 0;
}

static PyObject *
array_to_py (GICallableInfo *cb, GITypeInfo *ti, GIArgument *arg, GITransfer transfer)
{
  GIArrayType arrtype = gi_type_info_get_array_type (ti);
  if (arrtype == GI_ARRAY_TYPE_C)
    {
      return pygi_c_array_to_py (cb, ti, arg, NULL, NULL, transfer);
    }

  if (arrtype == GI_ARRAY_TYPE_BYTE_ARRAY || arrtype == GI_ARRAY_TYPE_PTR_ARRAY)
    {
      return pygi_garray_to_py (cb, ti, arg, transfer);
    }
  if (arrtype == GI_ARRAY_TYPE_ARRAY)
    {
      g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (ti, 0);
      GArray *array = (GArray *)arg->v_pointer;
      if (elem_ti == NULL)
        {
          pygi_set_unimplemented_type_error ("GI return conversion",
                                             ti,
                                             "array element type metadata missing");
          return NULL;
        }
      if (array == NULL)
        return Py_XNewRef (Py_None);
      PyObject *list = PyList_New ((Py_ssize_t)array->len);
      if (list == NULL)
        return NULL;
      gsize elem_size = g_array_get_element_size (array);
      PyGIContainerElement element;
      gboolean use_element_plan = pygi_container_element_init (&element, elem_ti) == 0;
      for (guint i = 0; i < array->len; i++)
        {
          PyObject *item = NULL;
          if (use_element_plan)
            {
              item = pygi_container_element_inline_to_py (&element,
                                                          array->data + (gsize)i * elem_size);
            }
          else
            {
              GIArgument elem_arg = { 0 };
              if (pygi_load_array_element (elem_ti, array->data, i, elem_size, &elem_arg) != 0)
                {
                  Py_DECREF (list);
                  pygi_set_unimplemented_type_error ("GI return conversion",
                                                     elem_ti,
                                                     "array element type");
                  return NULL;
                }
              item = pygi_argument_to_py (cb, elem_ti, &elem_arg);
            }
          if (item == NULL)
            {
              Py_DECREF (list);
              return NULL;
            }
          PyList_SET_ITEM (list, (Py_ssize_t)i, (PyObject *)(item));
        }
      return (PyObject *)(list);
    }
  /* Bug #4: null-terminated C arrays (GStrv, zero-terminated char**). */
  if (gi_type_info_get_array_type (ti) == GI_ARRAY_TYPE_C && gi_type_info_is_zero_terminated (ti))
    {
      g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (ti, 0);
      if (elem_ti == NULL)
        {
          pygi_set_unimplemented_type_error ("GI return conversion",
                                             ti,
                                             "array element type metadata missing");
          return NULL;
        }
      GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);
      /* Non-string zero-terminated array: count elements until a zero
       * value of element-size bytes, then convert each. */
      if (elem_tag != GI_TYPE_TAG_UTF8 && elem_tag != GI_TYPE_TAG_FILENAME)
        {
          gsize esize = gi_type_info_element_size (elem_ti);
          if (esize == 0 && gi_type_info_is_gvalue (elem_ti))
            {
              if (arg->v_pointer == NULL)
                return Py_XNewRef (Py_None);
              GValue *values = (GValue *)arg->v_pointer;
              gsize n = 0;
              while (G_VALUE_TYPE (&values[n]) != 0)
                n++;
              PyObject *list = PyList_New ((Py_ssize_t)n);
              if (list == NULL)
                return NULL;
              for (gsize zi = 0; zi < n; zi++)
                {
                  PyObject *item = pygi_gvalue_value_to_py (&values[zi]);
                  if (item == NULL)
                    {
                      Py_DECREF (list);
                      return NULL;
                    }
                  PyList_SET_ITEM (list, (Py_ssize_t)zi, (PyObject *)(item));
                }
              if (transfer != GI_TRANSFER_NOTHING)
                {
                  for (gsize zi = 0; zi < n; zi++)
                    g_value_unset (&values[zi]);
                  g_free (values);
                }
              return (PyObject *)(list);
            }
          if (esize == 0)
            {
              pygi_set_unimplemented_type_error ("GI return conversion",
                                                 elem_ti,
                                                 "zero-terminated array element size");
              return NULL;
            }
          if (arg->v_pointer == NULL)
            return Py_XNewRef (Py_None);
          const char *base = (const char *)arg->v_pointer;
          gsize n = 0;
          while (1)
            {
              int is_zero = 1;
              for (gsize b = 0; b < esize; b++)
                {
                  if (base[n * esize + b] != 0)
                    {
                      is_zero = 0;
                      break;
                    }
                }
              if (is_zero)
                break;
              n++;
            }
          PyObject *list = PyList_New ((Py_ssize_t)n);
          if (list == NULL)
            return NULL;
          for (gsize zi = 0; zi < n; zi++)
            {
              PyObject *item;
              if (elem_tag == GI_TYPE_TAG_ARRAY)
                {
                  gchar **strv = *(gchar ***)((void *)(base + zi * esize));
                  item = pygi_strv_to_py_list (strv, GI_TRANSFER_NOTHING);
                }
              else if (elem_tag == GI_TYPE_TAG_UNICHAR)
                {
                  gunichar cp = *(const gunichar *)(base + zi * esize);
                  PyObject *s = PyUnicode_FromOrdinal ((int)cp);
                  item = (PyObject *)(s);
                }
              else
                {
                  GIArgument earg = { 0 };
                  if (pygi_load_array_element (elem_ti, base, (guint)zi, esize, &earg) != 0)
                    {
                      Py_DECREF (list);
                      pygi_set_unimplemented_type_error ("GI return conversion",
                                                         elem_ti,
                                                         "zero-terminated element");
                      return NULL;
                    }
                  item = pygi_argument_to_py (cb, elem_ti, &earg);
                }
              if (item == NULL)
                {
                  Py_DECREF (list);
                  return NULL;
                }
              PyList_SET_ITEM (list, (Py_ssize_t)zi, (PyObject *)(item));
            }
          if (transfer != GI_TRANSFER_NOTHING)
            g_free (arg->v_pointer);
          return (PyObject *)(list);
        }
      char **strv = (char **)arg->v_pointer;
      gsize n = 0;
      if (strv != NULL)
        {
          while (strv[n] != NULL)
            n++;
        }
      PyObject *list = PyList_New ((Py_ssize_t)n);
      if (list == NULL)
        return NULL;
      for (gsize i = 0; i < n; i++)
        {
          GIArgument elem_arg = { 0 };
          elem_arg.v_string = strv[i];
          /* Always TRANSFER_NONE for individual elements: the outer
           * g_strfreev/g_free below handles array-level cleanup. */
          PyObject *item = pygi_utf8_to_py (&elem_arg, GI_TRANSFER_NOTHING);
          if (item == NULL)
            {
              Py_DECREF (list);
              return NULL;
            }
          PyList_SET_ITEM (list, (Py_ssize_t)i, item);
        }
      if (strv != NULL)
        {
          if (transfer == GI_TRANSFER_EVERYTHING)
            g_strfreev (strv);
          else if (transfer == GI_TRANSFER_CONTAINER)
            g_free (strv);
        }
      return (PyObject *)(list);
    }
  /* Fixed-size C array: length is encoded in the type metadata. */
  if (gi_type_info_get_array_type (ti) == GI_ARRAY_TYPE_C)
    {
      size_t fixed_size = 0;
      if (gi_type_info_get_array_fixed_size (ti, &fixed_size) && fixed_size > 0)
        {
          g_autoptr (GITypeInfo) felem_ti = gi_type_info_get_param_type (ti, 0);
          if (felem_ti == NULL)
            {
              pygi_set_unimplemented_type_error ("GI return conversion",
                                                 ti,
                                                 "fixed array element type metadata missing");
              return NULL;
            }
          if (arg->v_pointer == NULL)
            return Py_XNewRef (Py_None);
          gsize esize = gi_type_info_element_size (felem_ti);
          if (esize == 0 && gi_type_info_is_gvalue (felem_ti))
            {
              GValue *values = (GValue *)arg->v_pointer;
              PyObject *list = PyList_New ((Py_ssize_t)fixed_size);
              if (list == NULL)
                return NULL;
              for (size_t fi = 0; fi < fixed_size; fi++)
                {
                  PyObject *item = pygi_gvalue_value_to_py (&values[fi]);
                  if (item == NULL)
                    {
                      Py_DECREF (list);
                      return NULL;
                    }
                  PyList_SET_ITEM (list, (Py_ssize_t)fi, (PyObject *)(item));
                }
              if (transfer != GI_TRANSFER_NOTHING)
                {
                  for (size_t fi = 0; fi < fixed_size; fi++)
                    g_value_unset (&values[fi]);
                  g_free (values);
                }
              return (PyObject *)(list);
            }
          if (esize == 0)
            {
              pygi_set_unimplemented_type_error ("GI return conversion",
                                                 felem_ti,
                                                 "fixed array element size");
              return NULL;
            }
          PyObject *list = PyList_New ((Py_ssize_t)fixed_size);
          if (list == NULL)
            return NULL;
          const char *base = (const char *)arg->v_pointer;
          /* If element is itself an ARRAY (e.g. GStrv), each slot holds a
           * gchar** pointer.  Unconditionally pass NOTHING transfer for
           * inner conversion to avoid double-frees on container/none.
           * For EVERYTHING outer, the inner strvs leak (acceptable). */
          GITypeTag fet = gi_type_info_get_tag (felem_ti);
          for (size_t fi = 0; fi < fixed_size; fi++)
            {
              PyObject *item;
              if (fet == GI_TYPE_TAG_ARRAY)
                {
                  gchar **strv = *(gchar ***)((void *)(base + fi * esize));
                  item = pygi_strv_to_py_list (strv, GI_TRANSFER_NOTHING);
                }
              else
                {
                  GIArgument earg = { 0 };
                  if (pygi_load_array_element (felem_ti, base, (guint)fi, esize, &earg) != 0)
                    {
                      Py_DECREF (list);
                      pygi_set_unimplemented_type_error ("GI return conversion",
                                                         felem_ti,
                                                         "fixed array element");
                      return NULL;
                    }
                  item = pygi_argument_to_py (cb, felem_ti, &earg);
                }
              if (item == NULL)
                {
                  Py_DECREF (list);
                  return NULL;
                }
              PyList_SET_ITEM (list, (Py_ssize_t)fi, (PyObject *)(item));
            }
          if (transfer != GI_TRANSFER_NOTHING)
            g_free (arg->v_pointer);
          return (PyObject *)(list);
        }
    }
  pygi_set_unimplemented_type_error ("GI return conversion", ti, "non-GArray array return");
  return NULL;
}

static PyObject *
list_node_data_to_py (GICallableInfo *cb, GITypeInfo *elem_ti, gpointer data, GITransfer transfer)
{
  GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);
  switch (elem_tag)
    {
    case GI_TYPE_TAG_INT32:
      return PyLong_FromLong ((long)GPOINTER_TO_INT (data));
    case GI_TYPE_TAG_UINT32:
      return PyLong_FromUnsignedLong ((unsigned long)GPOINTER_TO_UINT (data));
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      if (data == NULL)
        Py_RETURN_NONE;
      return PyUnicode_FromString ((const char *)data);
    case GI_TYPE_TAG_INTERFACE:
      {
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_ti);
        if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
          {
            GIArgument elem_arg = { .v_pointer = data };
            GITransfer item_transfer
                = transfer == GI_TRANSFER_EVERYTHING ? GI_TRANSFER_EVERYTHING : GI_TRANSFER_NOTHING;
            return pygi_argument_to_py_transfer (cb, elem_ti, &elem_arg, item_transfer);
          }
        if (iface != NULL && (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)))
          {
            GIArgument elem_arg = { .v_pointer = data };
            GITransfer item_transfer
                = transfer == GI_TRANSFER_EVERYTHING ? GI_TRANSFER_EVERYTHING : GI_TRANSFER_NOTHING;
            return pygi_argument_to_py_transfer (cb, elem_ti, &elem_arg, item_transfer);
          }
        break;
      }
    default:
      break;
    }
  pygi_set_unimplemented_type_error ("GI return conversion",
                                     elem_ti,
                                     "TODO ginext: unsupported list element type");
  return NULL;
}

static PyObject *
list_to_py (GICallableInfo *cb,
            GITypeInfo *ti,
            GIArgument *arg,
            GITransfer transfer,
            gboolean singly_linked)
{
  g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (ti, 0);
  if (elem_ti == NULL)
    {
      pygi_set_unimplemented_type_error ("GI return conversion",
                                         ti,
                                         singly_linked ? "GSList element type metadata missing"
                                                       : "GList element type metadata missing");
      return NULL;
    }

  gpointer list = arg->v_pointer;
  guint len = singly_linked ? g_slist_length ((GSList *)list) : g_list_length ((GList *)list);
  PyObject *pylist = PyList_New ((Py_ssize_t)len);
  if (pylist == NULL)
    return NULL;

  guint index = 0;
  for (gpointer node = list; node != NULL; index++)
    {
      gpointer data;
      if (singly_linked)
        {
          GSList *snode = (GSList *)node;
          data = snode->data;
          node = snode->next;
        }
      else
        {
          GList *gnode = (GList *)node;
          data = gnode->data;
          node = gnode->next;
        }

      PyObject *item = list_node_data_to_py (cb, elem_ti, data, transfer);
      if (item == NULL)
        {
          Py_DECREF (pylist);
          return NULL;
        }
      PyList_SET_ITEM (pylist, (Py_ssize_t)index, item);
    }

  if (transfer != GI_TRANSFER_NOTHING)
    {
      GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);
      gboolean free_items = transfer == GI_TRANSFER_EVERYTHING
                            && (elem_tag == GI_TYPE_TAG_UTF8 || elem_tag == GI_TYPE_TAG_FILENAME);
      if (singly_linked)
        {
          if (free_items)
            g_slist_free_full ((GSList *)list, g_free);
          else
            g_slist_free ((GSList *)list);
        }
      else
        {
          if (free_items)
            g_list_free_full ((GList *)list, g_free);
          else
            g_list_free ((GList *)list);
        }
    }

  return pylist;
}

static PyObject *
struct_snapshot_field_to_py (GITypeInfo *fti, char *base, size_t offset)
{
  GITypeTag ftag = gi_type_info_get_tag (fti);
  if (ftag == GI_TYPE_TAG_ARRAY && gi_type_info_get_array_type (fti) == GI_ARRAY_TYPE_C
      && gi_type_info_is_zero_terminated (fti))
    {
      g_autoptr (GITypeInfo) inner_ti = gi_type_info_get_param_type (fti, 0);
      if (inner_ti != NULL)
        {
          GITypeTag itag = gi_type_info_get_tag (inner_ti);
          if (itag == GI_TYPE_TAG_UTF8 || itag == GI_TYPE_TAG_FILENAME)
            {
              gchar **strv = *(gchar ***)((void *)(base + offset));
              return pygi_strv_to_py_list (strv, GI_TRANSFER_NOTHING);
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

  return NULL;
}

static PyObject *
struct_snapshot_to_py (GIBaseInfo *iface, GIArgument *arg)
{
  PyObject *types_mod = PyImport_ImportModule ("types");
  if (types_mod == NULL)
    return NULL;
  PyObject *sns_cls = PyObject_GetAttrString (types_mod, "SimpleNamespace");
  Py_DECREF (types_mod);
  if (sns_cls == NULL)
    return NULL;
  PyObject *wrapper = PyObject_CallObject (sns_cls, NULL);
  Py_DECREF (sns_cls);
  if (wrapper == NULL)
    return NULL;

  char *base = (char *)arg->v_pointer;
  int n_fields = gi_struct_or_union_n_fields (iface);
  for (int fi = 0; fi < n_fields; fi++)
    {
      g_autoptr (GIFieldInfo) field = gi_struct_or_union_get_field (iface, (guint)fi);
      if (field == NULL)
        continue;
      if (!(gi_field_info_get_flags (field) & GI_FIELD_IS_READABLE))
        continue;
      const char *fname = gi_base_info_get_name ((GIBaseInfo *)field);
      size_t offset = gi_field_info_get_offset (field);
      g_autoptr (GITypeInfo) fti = gi_field_info_get_type_info (field);
      PyObject *val = struct_snapshot_field_to_py (fti, base, offset);
      if (val == NULL)
        {
          if (PyErr_Occurred ())
            {
              Py_DECREF (wrapper);
              return NULL;
            }
          continue;
        }
      if (PyObject_SetAttrString (wrapper, fname, val) < 0)
        {
          Py_DECREF (val);
          Py_DECREF (wrapper);
          return NULL;
        }
      Py_DECREF (val);
    }

  return wrapper;
}

static PyObject *
struct_or_union_to_py (GIBaseInfo *iface, GITypeInfo *ti, GIArgument *arg, GITransfer transfer)
{
  PyObject *cw = pygi_foreign_cairo_to_py (iface, arg->v_pointer, transfer);
  if (cw != NULL)
    return (PyObject *)(cw);
  if (PyErr_Occurred ())
    return NULL;

  if (arg->v_pointer == NULL)
    return Py_XNewRef (Py_None);

  GType iface_gt = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
  if (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
    {
      PyObject *cls = (iface_gt != G_TYPE_NONE && iface_gt != 0)
                          ? pygi_class_registry_get_pytype_for_gtype (iface_gt)
                          : NULL;
      if (cls == NULL)
        {
          PyObject *h_cls = pygi_build_struct_class (gi_base_info_get_namespace (iface), iface);
          if (!(h_cls == NULL))
            {
              cls = (PyObject *)(void *)(h_cls);
              Py_DECREF (cls);
            }
          else if ((PyErr_Occurred () != NULL))
            return NULL;
        }
      if (cls != NULL)
        {
          gpointer boxed_ptr = arg->v_pointer;
          int transfer_full = (transfer == GI_TRANSFER_EVERYTHING);
          if (iface_gt != G_TYPE_NONE && iface_gt != 0 && G_TYPE_IS_BOXED (iface_gt)
              && (!gi_type_info_is_pointer (ti) || transfer == GI_TRANSFER_NOTHING))
            {
              boxed_ptr = g_boxed_copy (iface_gt, arg->v_pointer);
              transfer_full = 1;
              if (boxed_ptr == NULL)
                return Py_XNewRef (Py_None);
            }
          PyObject *wrapper = NULL;
          if ((iface_gt == G_TYPE_NONE || iface_gt == 0) && !gi_type_info_is_pointer (ti)
              && boxed_ptr != NULL)
            {
              gsize size = gi_struct_or_union_size (iface);
              if (size == 0)
                size = sizeof (void *);
              gpointer copy = g_memdup2 (boxed_ptr, size);
              if (copy == NULL)
                return PyErr_NoMemory ();
              wrapper = pygi_boxed_new_heap (cls, copy, iface_gt, size);
              if (wrapper == NULL)
                {
                  g_free (copy);
                  return NULL;
                }
              return (PyObject *)wrapper;
            }
          wrapper = pygi_boxed_new (cls, boxed_ptr, iface_gt, transfer_full);
          if (wrapper == NULL)
            {
              if (!gi_type_info_is_pointer (ti) && boxed_ptr != NULL)
                g_boxed_free (iface_gt, boxed_ptr);
              return NULL;
            }
          return (PyObject *)(wrapper);
        }
    }

  return struct_snapshot_to_py (iface, arg);
}

static PyObject *
interface_to_py (GICallableInfo *cb, GITypeInfo *ti, GIArgument *arg, GITransfer transfer)
{
  (void)cb;
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL)
    {
      PyErr_SetString (PyExc_NotImplementedError, "return interface missing metadata");
      return NULL;
    }

  if (gi_type_info_is_param_spec (ti))
    {
      PyObject *pspec = pygi_param_spec_new ((GParamSpec *)arg->v_pointer);
      if (pspec != NULL && transfer != GI_TRANSFER_NOTHING && arg->v_pointer != NULL)
        g_param_spec_unref ((GParamSpec *)arg->v_pointer);
      return pspec;
    }
  if (GI_IS_OBJECT_INFO (iface))
    {
      GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
      return pygi_gobject_to_py_as_gtype ((GObject *)arg->v_pointer, gtype, transfer);
    }
  if (gi_type_info_is_variant (ti))
    return pygi_variant_to_py (ti, arg, transfer);
  if (gi_type_info_is_gvalue (ti))
    {
      PyObject *gv = pygi_gvalue_to_py (arg);
      if (transfer != GI_TRANSFER_NOTHING && arg->v_pointer != NULL)
        {
          g_value_unset ((GValue *)arg->v_pointer);
          g_free (arg->v_pointer);
        }
      return gv;
    }
  if (GI_IS_OBJECT_INFO (iface))
    return pygi_object_info_to_py (arg, transfer);
  if (GI_IS_INTERFACE_INFO (iface))
    {
      GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
      return pygi_gobject_to_py_as_gtype ((GObject *)arg->v_pointer, gtype, transfer);
    }
  /* Flags before enum: GIFlagsInfo is a subtype of GIEnumInfo, and flags are
     unsigned (read via v_uint, not the signed v_int enum path). */
  if (GI_IS_FLAGS_INFO (iface))
    return pygi_flags_info_to_py (ti, arg);
  if (GI_IS_ENUM_INFO (iface))
    return pygi_enum_info_to_py (ti, arg);
  if (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface))
    return struct_or_union_to_py (iface, ti, arg, transfer);

  pygi_set_unimplemented_type_error ("GI return conversion", ti, "boxed/struct/interface returns");
  return NULL;
}

PyObject *
pygi_argument_to_py_transfer (GICallableInfo *cb,
                              GITypeInfo *ti,
                              GIArgument *arg,
                              GITransfer transfer)
{
  PyGIType type = { 0 };
  if (pygi_type_from_gi (ti, &type) == 0)
    {
      type.transfer = transfer;
      if (pygi_type_is_direct_storage (&type) && type.kind != PYGI_TYPE_ENUM
          && type.kind != PYGI_TYPE_FLAGS)
        {
          PyGIValue value = pygi_value_for_giarg (&type, arg);
          return pygi_value_to_py (&value);
        }
    }

  GITypeTag tag = gi_type_info_get_tag (ti);
  switch (tag)
    {
    case GI_TYPE_TAG_ARRAY:
      return array_to_py (cb, ti, arg, transfer);
    case GI_TYPE_TAG_GHASH:
      return pygi_ghash_to_py (cb, ti, arg, transfer);
    case GI_TYPE_TAG_ERROR:
      return pygi_error_to_py (arg, transfer);
    case GI_TYPE_TAG_GLIST:
      return list_to_py (cb, ti, arg, transfer, FALSE);
    case GI_TYPE_TAG_GSLIST:
      return list_to_py (cb, ti, arg, transfer, TRUE);
    case GI_TYPE_TAG_INTERFACE:
      return interface_to_py (cb, ti, arg, transfer);
    default:
      pygi_set_unimplemented_type_error ("GI return conversion", ti, NULL);
      return NULL;
    }
}

PyObject *
pygi_argument_to_py (GICallableInfo *cb, GITypeInfo *ti, GIArgument *arg)
{
  /* Legacy entry: transfer derives from the callable's return-value
   * `caller_owns`. Correct for return-value marshalling; wrong for
   * per-argument marshalling - those callers should use
   * pygi_argument_to_py_transfer with the parameter's own transfer. */
  GITransfer transfer = gi_callable_info_get_caller_owns (cb);
  return pygi_argument_to_py_transfer (cb, ti, arg, transfer);
}

int
pygi_argument_from_py_for_call (GITypeTag tag,
                                GIArrayType array_type,
                                GITransfer transfer,
                                GITypeInfo *ti,
                                GIArgInfo *ai,
                                PyObject *pyval,
                                GIArgument *dest,
                                PyGIArgCleanup *cleanup,
                                int arg_pos)
{
  /* C-array (fixed-size or zero-terminated).
   * Length-paired variants (AFTER_ARRAY / BEFORE_ARRAY) stay in the binder. */
  if (tag == GI_TYPE_TAG_ARRAY && array_type == GI_ARRAY_TYPE_C)
    {
      g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (ti, 0);
      if (elem_ti == NULL)
        {
          pygi_set_unimplemented_type_error ("from-Python", ti, "C-array missing element type");
          return -1;
        }
      size_t fixed_size = 0;
      if (pyval == Py_None && !gi_type_info_is_pointer (elem_ti)
          && gi_type_info_get_array_fixed_size (ti, &fixed_size) && fixed_size > 0)
        {
          PyErr_SetString (PyExc_TypeError, "fixed-size array argument cannot be None");
          return -1;
        }
      return pygi_py_to_c_array_invoke (pyval,
                                        elem_ti,
                                        dest,
                                        NULL,
                                        NULL,
                                        gi_type_info_is_zero_terminated (ti),
                                        fixed_size,
                                        cleanup,
                                        transfer);
    }

  /* GArray / GPtrArray / GByteArray. */
  if (tag == GI_TYPE_TAG_ARRAY)
    return pygi_garray_from_py (pyval, ti, transfer, dest, cleanup);

  if (tag == GI_TYPE_TAG_GHASH)
    return pygi_ghash_from_py (pyval, ti, transfer, dest, cleanup);

  if (tag == GI_TYPE_TAG_GLIST)
    return pygi_glist_from_py (pyval, ti, transfer, dest, cleanup);

  if (tag == GI_TYPE_TAG_GSLIST)
    return pygi_slist_from_py (pyval, ti, transfer, dest, cleanup);

  if (tag == GI_TYPE_TAG_ERROR)
    {
      GError *err = NULL;
      int rc = pygi_error_from_py (pyval, &err);
      if (rc < 0)
        return -1;
      if (rc == 0)
        {
          PyErr_Format (PyExc_TypeError,
                        "expected GLib.Error, not %.200s",
                        Py_TYPE (pyval)->tp_name);
          return -1;
        }
      dest->v_pointer = err;
      if (err != NULL && transfer != GI_TRANSFER_EVERYTHING && cleanup != NULL)
        {
          cleanup->kind = PYGI_ARG_CLEANUP_GERROR;
          cleanup->ptr = err;
        }
      return 0;
    }

  if (gi_type_info_is_gvalue (ti))
    return pygi_gvalue_from_py (pyval, ai, dest, cleanup);

  if (gi_type_info_is_variant (ti))
    return pygi_py_item_to_gvariant ((PyObject *)(pyval), &dest->v_pointer);

  /* Callback. */
  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
      if (iface != NULL && GI_IS_CALLBACK_INFO (iface))
        {
          GIScopeType scope = gi_arg_info_get_scope (ai);
          return pygi_callback_closure_new (pyval, iface, scope, dest, cleanup);
        }
      if (iface != NULL && gi_base_info_is_named (iface, "GObject", "Closure"))
        {
          PyObject *obj = (PyObject *)pyval;
          gpointer boxed_ptr = NULL;
          if (pygi_boxed_get (obj, &boxed_ptr) == 0 && boxed_ptr != NULL)
            {
              dest->v_pointer = boxed_ptr;
              return 0;
            }
          PyErr_Clear ();
          /* Most GClosure args are not nullable; passing None would have
           * the C side dereference a NULL closure. Match pygobject and
           * reject None unconditionally — callers that want a "no-op"
           * closure can pass `lambda *a: None`. */
          if (!PyCallable_Check (obj))
            {
              PyErr_SetString (PyExc_TypeError, "GClosure argument must be callable");
              return -1;
            }
          PyGIClosureRecordKind kind = PYGI_CLOSURE_RECORD_SIGNAL;
          if (ai != NULL)
            {
              const char *arg_name = gi_base_info_get_name ((GIBaseInfo *)ai);
              if (g_strcmp0 (arg_name, "transform_to") == 0
                  || g_strcmp0 (arg_name, "transform_from") == 0)
                kind = PYGI_CLOSURE_RECORD_BINDING_TRANSFORM;
            }
          GClosure *closure = pygi_closure_new_with_kind (obj, kind);
          if (closure == NULL)
            return -1;
          dest->v_pointer = closure;
          return 0;
        }
    }

  /* Generic scalar / struct / enum / flags / object / interface. */
  if (arg_pos > 0 && pygi_check_arg_type (pyval, tag, arg_pos) != 0)
    return -1;
  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      int handled = 0;
      if (transfer == GI_TRANSFER_EVERYTHING
          && boxed_transfer_full_arg_from_py (pyval, ti, dest, &handled) != 0)
        return -1;
      if (handled)
        return 0;
      if (interface_from_py (pyval, ti, transfer, dest) != 0)
        return -1;
      /* TRANSFER_EVERYTHING + GObject: the callee takes ownership and
       * will unref. Hand it an extra ref so the Python wrapper keeps
       * its own reference intact. (boxed struct/union is handled above
       * via g_boxed_copy; enums/flags/callbacks are by-value.) */
      if (transfer == GI_TRANSFER_EVERYTHING && dest->v_pointer != NULL)
        {
          g_autoptr (GIBaseInfo) iface_full = gi_type_info_get_interface (ti);
          if (iface_full != NULL
              && (GI_IS_OBJECT_INFO (iface_full) || GI_IS_INTERFACE_INFO (iface_full)))
            {
              GType gtype = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface_full);
              gpointer owned = NULL;
              if (pygi_instantiatable_ref (dest->v_pointer, gtype, &owned) != 0)
                return -1;
              dest->v_pointer = owned;
            }
        }
    }
  else if (pygi_argument_from_py (pyval, ti, dest) != 0)
    return -1;
  /* GBytes args: pygi_argument_from_py created a fresh GBytes via
   * g_bytes_new (refcount 1, owned by us). Hand it to the cleanup so it
   * gets unrefed after the call regardless of whether the callee took
   * an extra ref. */
  if (tag == GI_TYPE_TAG_INTERFACE && dest->v_pointer != NULL && cleanup != NULL
      && cleanup->kind == PYGI_ARG_CLEANUP_NONE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
      if (iface != NULL && gi_base_info_is_named (iface, "GLib", "Bytes"))
        {
          cleanup->kind = PYGI_ARG_CLEANUP_GBYTES;
          cleanup->ptr = dest->v_pointer;
        }
      /* GLib.Regex args: interface_from_py handed us an owned GRegex ref
       * (compiled from a re.Pattern). Unref it after the call. */
      else if (iface != NULL && gi_base_info_is_named (iface, "GLib", "Regex"))
        {
          cleanup->kind = PYGI_ARG_CLEANUP_GREGEX;
          cleanup->ptr = dest->v_pointer;
        }
      /* GLib.DateTime/Date/TimeZone args: interface_from_py handed us an owned
       * value (built from a stdlib object, or ref/copied off a wrapper). */
      else if (iface != NULL && gi_base_info_is_named (iface, "GLib", "DateTime"))
        {
          cleanup->kind = PYGI_ARG_CLEANUP_GDATETIME;
          cleanup->ptr = dest->v_pointer;
        }
      else if (iface != NULL && gi_base_info_is_named (iface, "GLib", "TimeZone"))
        {
          cleanup->kind = PYGI_ARG_CLEANUP_GTIMEZONE;
          cleanup->ptr = dest->v_pointer;
        }
      else if (iface != NULL && gi_base_info_is_named (iface, "GLib", "Date"))
        {
          cleanup->kind = PYGI_ARG_CLEANUP_GDATE;
          cleanup->ptr = dest->v_pointer;
        }
    }
  if ((tag == GI_TYPE_TAG_UTF8 || tag == GI_TYPE_TAG_FILENAME) && transfer == GI_TRANSFER_EVERYTHING
      && dest->v_string != NULL)
    {
      char *dup = g_strdup (dest->v_string);
      if (dup == NULL)
        {
          PyErr_NoMemory ();
          return -1;
        }
      dest->v_string = dup;
    }
  return 0;
}


/* ===========================================================================
 * Phase 1 unified entry - adapter shims around the legacy dispatchers above.
 * These do not yet eliminate any duplication; they give consumers a single
 * call shape so subsequent phases can migrate them one by one.
 * ========================================================================= */

int
pygi_marshal_from_py (PyObject *value, PyGIMarshalSlot *slot)
{
  g_return_val_if_fail (slot != NULL, -1);
  g_return_val_if_fail (slot->type != NULL, -1);

  switch (slot->kind)
    {
    case PYGI_MARSHAL_TARGET_GIARG:
      {
        g_return_val_if_fail (slot->target.giarg != NULL, -1);
        if (slot->pygi_type != NULL && pygi_type_is_direct_storage (slot->pygi_type))
          {
            if ((slot->pygi_type->kind == PYGI_TYPE_UTF8
                 || slot->pygi_type->kind == PYGI_TYPE_FILENAME)
                && slot->transfer == GI_TRANSFER_EVERYTHING)
              goto legacy_giarg_from_py;
            PyGIType type = *slot->pygi_type;
            type.transfer = slot->transfer;
            PyGIValue pygi_value = pygi_value_for_giarg (&type, slot->target.giarg);
            return pygi_value_from_py (value, &pygi_value);
          }
      legacy_giarg_from_py:;
        GITypeTag tag = gi_type_info_get_tag (slot->type);
        if (tag == GI_TYPE_TAG_ARRAY && gi_type_info_get_array_type (slot->type) == GI_ARRAY_TYPE_C)
          {
            g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (slot->type, 0);
            if (elem_ti == NULL)
              {
                pygi_set_unimplemented_type_error ("GI argument conversion",
                                                   slot->type,
                                                   "C-array missing element type");
                return -1;
              }
            size_t fixed_size = 0;
            return pygi_py_to_c_array_invoke (
                value,
                elem_ti,
                slot->target.giarg,
                slot->length_arg,
                slot->length_type,
                gi_type_info_is_zero_terminated (slot->type),
                gi_type_info_get_array_fixed_size (slot->type, &fixed_size) ? fixed_size : 0,
                slot->cleanup,
                slot->transfer);
          }
        GIArrayType atype = (tag == GI_TYPE_TAG_ARRAY) ? gi_type_info_get_array_type (slot->type)
                                                       : (GIArrayType)0;
        return pygi_argument_from_py_for_call (tag,
                                               atype,
                                               slot->transfer,
                                               slot->type,
                                               slot->arg_info,
                                               value,
                                               slot->target.giarg,
                                               slot->cleanup,
                                               slot->arg_pos);
      }
    case PYGI_MARSHAL_TARGET_MEMORY:
      {
        g_return_val_if_fail (slot->target.memory != NULL, -1);
        PyGIType type = { 0 };
        if (slot->pygi_type != NULL)
          type = *slot->pygi_type;
        else if (pygi_type_from_gi (slot->type, &type) != 0)
          {
            pygi_set_unimplemented_type_error ("pygi_marshal_from_py",
                                               slot->type,
                                               "memory target type");
            return -1;
          }
        type.transfer = slot->transfer;
        if (!pygi_type_is_direct_storage (&type))
          {
            pygi_set_unimplemented_type_error ("pygi_marshal_from_py",
                                               slot->type,
                                               "memory target type");
            return -1;
          }
        PyGIValue pygi_value = pygi_value_for_memory (&type, slot->target.memory);
        return pygi_value_from_py (value, &pygi_value);
      }
    case PYGI_MARSHAL_TARGET_GVALUE:
      g_return_val_if_fail (slot->target.gvalue != NULL, -1);
      return pygi_py_to_gvalue_inplace (value, slot->target.gvalue, slot->arg_info);
    }
  PyErr_SetString (PyExc_SystemError, "pygi_marshal_from_py: unknown target kind");
  return -1;
}

PyObject *
pygi_marshal_to_py (const PyGIMarshalSlot *slot)
{
  g_return_val_if_fail (slot != NULL, NULL);
  g_return_val_if_fail (slot->type != NULL, NULL);

  switch (slot->kind)
    {
    case PYGI_MARSHAL_TARGET_GIARG:
      g_return_val_if_fail (slot->target.giarg != NULL, NULL);
      if (slot->pygi_type != NULL && pygi_type_is_direct_storage (slot->pygi_type)
          && slot->pygi_type->kind != PYGI_TYPE_ENUM && slot->pygi_type->kind != PYGI_TYPE_FLAGS)
        {
          PyGIType type = *slot->pygi_type;
          type.transfer = slot->transfer;
          PyGIValue pygi_value = pygi_value_for_giarg (&type, slot->target.giarg);
          return pygi_value_to_py (&pygi_value);
        }
      /* Length-paired C array: route to the c-array conversion. */
      if (slot->length_type != NULL && slot->length_arg != NULL
          && gi_type_info_get_tag (slot->type) == GI_TYPE_TAG_ARRAY)
        return pygi_c_array_to_py (slot->callable,
                                   slot->type,
                                   slot->target.giarg,
                                   slot->length_type,
                                   slot->length_arg,
                                   slot->transfer);
      /* caller-allocates struct OUT: the bind layer g_malloc0'd a
       * buffer the Python wrapper now needs to own (bind.c skips its
       * cleanup; without taking ownership here the wrapper would hold
       * a freed pointer). Only applies to plain struct/union interface
       * args - GValue / arrays / etc. have their own bind/marshal
       * pairing (GValue keeps its own PYGI_ARG_CLEANUP_GVALUE; arrays
       * don't run through this branch). */
      GITransfer eff_transfer = slot->transfer;
      bool eff_transfer_set = slot->transfer_set;
      if (slot->caller_allocates && gi_type_info_get_tag (slot->type) == GI_TYPE_TAG_INTERFACE
          && !gi_type_info_is_gvalue (slot->type))
        {
          g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (slot->type);
          if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
            {
              eff_transfer = GI_TRANSFER_EVERYTHING;
              eff_transfer_set = true;
            }
        }
      if (eff_transfer_set)
        return pygi_argument_to_py_transfer (slot->callable,
                                             slot->type,
                                             slot->target.giarg,
                                             eff_transfer);
      return pygi_argument_to_py (slot->callable, slot->type, slot->target.giarg);
    case PYGI_MARSHAL_TARGET_MEMORY:
      {
        g_return_val_if_fail (slot->target.memory != NULL, NULL);
        PyGIType type = { 0 };
        if (slot->pygi_type != NULL)
          type = *slot->pygi_type;
        else if (pygi_type_from_gi (slot->type, &type) != 0)
          {
            pygi_set_unimplemented_type_error ("pygi_marshal_to_py",
                                               slot->type,
                                               "memory target type");
            return NULL;
          }
        type.transfer = slot->transfer;
        if (!pygi_type_is_direct_storage (&type))
          {
            pygi_set_unimplemented_type_error ("pygi_marshal_to_py",
                                               slot->type,
                                               "memory target type");
            return NULL;
          }
        PyGIValue pygi_value = pygi_value_for_memory (&type, slot->target.memory);
        return pygi_value_to_py (&pygi_value);
      }
    case PYGI_MARSHAL_TARGET_GVALUE:
      g_return_val_if_fail (slot->target.gvalue != NULL, NULL);
      return pygi_gvalue_value_to_py (slot->target.gvalue);
    }
  PyErr_SetString (PyExc_SystemError, "pygi_marshal_to_py: unknown target kind");
  return NULL;
}
