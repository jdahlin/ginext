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

/* invoke/bind.c - bind Python arguments into a GI invocation frame. */
#include "invoke/bind.h"

#include "GObject/Boxed.h"
#include "GObject/Object.h"
#include "marshal/c-array.h"
#include "marshal/marshal.h"
#include "GObject/Closure.h"
#include "GObject/Fundamental.h"
#include "runtime/class-registry.h"
#include "GObject/Object-info.h"
#include "marshal/scalar.h"
#include "runtime/type-info.h"
#include "gimeta-helpers.h"

#include <stdint.h>
#include <string.h>
#include <glib.h>

/* Bare callable name after the last dot - "Foo.bar.baz" -> "baz".
 * Falls back to the input if there's no dot, or "?" if NULL. */
static const char *
pygi_bare_name (const char *qualified)
{
  if (qualified == NULL)
    return "?";
  const char *dot = strrchr (qualified, '.');
  return dot != NULL ? dot + 1 : qualified;
}

/* Set up OUT/INOUT storage for one GI arg at out_slot `ap->out_slot`.
 *
 * For caller_allocates: allocates the buffer, registers a cleanup, wires
 * out_args[slot] and out_values[slot], bumps out_tis_count, and returns a
 * non-NULL sentinel (the caller does NOT place an entry in in_args).
 *
 * For non-caller-allocates: points out_args[slot] at the type-specific
 * storage field inside out_values[slot], bumps out_tis_count, and returns
 * that storage pointer (caller places it in in_args for INOUT).
 *
 * Returns NULL on failure with a Python error set. */
static void *
bind_out_storage (PyGICallableDescriptor *descriptor,
                  PyGIInvokeFrame *frame,
                  GICallableInfo *cb,
                  const PyGIInvokePlan *plan,
                  const PyGIArgPlan *ap,
                  GIArgInfo *ai,
                  GITypeInfo *ti,
                  size_t i)
{
  ssize_t slot = ap->out_slot;
  (void)ai;

  if (ap->caller_allocates)
    {
      if (ap->caller_allocates_gvalue)
        {
          GValue *value = g_new0 (GValue, 1);
          frame->out_values[slot].v_pointer = value;
          frame->out_tis[slot] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)ti);
          frame->out_tis_count = (size_t)slot + 1;
          frame->out_args[slot].v_pointer = value;
          frame->cleanups[i].kind = PYGI_ARG_CLEANUP_GVALUE;
          frame->cleanups[i].ptr = value;
          return (void *)(intptr_t)1; /* sentinel: caller skips in_args entry */
        }
      if (ap->caller_allocates_size > 0)
        {
          void *buf = g_malloc0 (ap->caller_allocates_size);
          frame->out_values[slot].v_pointer = buf;
          frame->out_tis[slot] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)ti);
          frame->out_tis_count = (size_t)slot + 1;
          frame->out_args[slot].v_pointer = buf;
          /* NO cleanup: the OUT-marshal path takes ownership of `buf` by
           * wrapping with transfer_full=1 (see pygi_marshal_to_py's
           * caller_allocates override), and the Python wrapper frees via
           * g_boxed_free on dealloc. */
          return (void *)(intptr_t)1;
        }
      if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C)
        {
          if (ap->array_elem_ti != NULL)
            {
              gsize esz = ap->array_elem_size;
              size_t total = 0;
              size_t alloc_count = 1;
              if (ap->array_has_fixed_size && ap->array_fixed_size > 0 && esz > 0)
                {
                  total = ap->array_fixed_size * esz;
                  alloc_count = ap->array_fixed_size;
                }
              else if (ap->length_arg >= 0 && (size_t)ap->length_arg < plan->n_gi_args && esz > 0)
                {
                  ssize_t py_len = plan->args[ap->length_arg].py_arg_index;
                  (void)py_len; /* resolved by the outer caller if needed */
                }
              if (total > 0 || (ap->array_has_fixed_size && ap->array_fixed_size > 0 && esz > 0)
                  || (esz > 0 && ap->length_arg >= 0))
                {
                  void *buf = g_malloc0 (total > 0 ? total : esz);
                  frame->out_values[slot].v_pointer = buf;
                  frame->out_tis[slot] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)ti);
                  frame->out_tis_count = (size_t)slot + 1;
                  frame->out_args[slot].v_pointer = buf;
                  frame->cleanups[i].kind = PYGI_ARG_CLEANUP_FREE;
                  frame->cleanups[i].ptr = buf;
                  /* Caller-allocates flat array + paired (rewritten-to-IN)
                   * length: write the buffer's element count into the
                   * length's in_args slot. C reads it as the buffer size
                   * (the GIR's `direction=out` annotation for the length
                   * is wrong; C takes it BY VALUE). Also wire the
                   * IN-length back-reference so the return shaper can
                   * locate the length value when shaping the array. */
                  if (ap->length_arg >= 0)
                    {
                      size_t li = (size_t)ap->length_arg;
                      const PyGIArgPlan *lap = &plan->args[li];
                      if (lap->direction == GI_DIRECTION_IN && lap->in_slot >= 0)
                        {
                          frame->in_args[lap->in_slot].v_uint64 = (guint64)alloc_count;
                          frame->in_len_slot[li] = (size_t)lap->in_slot;
                          frame->in_len_ti[li]
                              = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)lap->cached_ti);
                        }
                    }
                  return (void *)(intptr_t)1;
                }
            }
        }
      if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_ARRAY)
        {
          if (ap->array_elem_ti != NULL)
            {
              gsize esz = ap->array_elem_size;
              if (esz > 0)
                {
                  GArray *ga = g_array_new (FALSE, FALSE, (guint)esz);
                  frame->out_values[slot].v_pointer = ga;
                  frame->out_tis[slot] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)ti);
                  frame->out_tis_count = (size_t)slot + 1;
                  frame->out_args[slot].v_pointer = ga;
                  frame->cleanups[i].kind = PYGI_ARG_CLEANUP_GARRAY;
                  frame->cleanups[i].ptr = ga;
                  return (void *)(intptr_t)1;
                }
            }
        }
      pygi_unsupported_fallback_shape (descriptor->qualified_name,
                                       cb,
                                       "OUT caller-allocates argument");
      return NULL;
    }

  /* Non-caller-allocates: wire out_args[slot] to the storage field. */
  void *storage_ptr = gi_argument_storage_pointer (ap->storage_tag, &frame->out_values[slot]);
  if (storage_ptr == NULL)
    {
      pygi_unsupported_fallback_shape (descriptor->qualified_name, cb, "OUT/INOUT argument type");
      return NULL;
    }
  frame->out_tis[slot] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)ti);
  frame->out_tis_count = (size_t)slot + 1;
  frame->out_args[slot].v_pointer = storage_ptr;
  return storage_ptr;
}

/* Convert one INOUT Python value into out_values[ap->out_slot] and wire
 * in_args[ap->in_slot] to the storage pointer set by bind_out_storage.
 * Returns 0 on success, -1 on error with a Python exception set. */
static int
bind_inout_value (PyGIInvokeFrame *frame,
                  const PyGIArgPlan *ap,
                  GIArgInfo *ai,
                  PyObject *pyval,
                  size_t i)
{
  ssize_t slot = ap->out_slot;
  PyGIMarshalSlot mslot = {
    .type = frame->out_tis[slot],
    .pygi_type = &ap->type,
    .transfer = ap->transfer,
    .kind = PYGI_MARSHAL_TARGET_GIARG,
    .target.giarg = &frame->out_values[slot],
    .cleanup = &frame->cleanups[i],
    .arg_info = ai,
    .arg_pos = 0,
  };
  if (pygi_marshal_from_py (pyval, &mslot) != 0)
    return -1;
  frame->in_args[ap->in_slot].v_pointer = frame->out_args[slot].v_pointer;
  return 0;
}

int
pygi_invoke_bind_args (PyGICallableDescriptor *descriptor,
                       PyGIInvokeFrame *frame,
                       GICallableInfo *cb,
                       const PyGIInvokePlan *plan,
                       PyObject *const *args,
                       size_t nargs)
{
  frame->bound_self = NULL;
  /* -- self -- */
  if (plan->has_self)
    {
      if (nargs == 0)
        {
          PyErr_SetString (PyExc_TypeError, "missing bound instance");
          return -1;
        }
      PyObject *self_py = (PyObject *)(void *)(args[0]);
      void *self_ptr = NULL;
      if (self_py == Py_None)
        {
          /* None as the instance is always a bug — GIR has no
           * may-be-null annotation for the self/instance slot, and the
           * C method always dereferences the pointer. Failing here
           * keeps a TypeError instead of a C-level deref crash. */
          PyErr_Format (PyExc_TypeError,
                        "%s: instance argument must not be None",
                        pygi_bare_name (descriptor->qualified_name));
          return -1;
        }
      else if (pygi_boxed_check (self_py))
        {
          /* Boxed-class instance method: self is the boxed pointer
           * (e.g. GResource*, GBytes*). Same shape as a GObject* on
           * the C ABI side - both are passed in the first arg slot. */
          gpointer p = NULL;
          if (pygi_boxed_get (self_py, &p) != 0)
            return -1;
          self_ptr = p;
          frame->bound_self = self_py;
        }
      else
        {
          gpointer self_obj = pygi_gobject_get (self_py);
          if (self_obj == NULL)
            {
              PyErr_Clear ();
              return pygi_raise_gobject_type_error_for_gtype_named (G_TYPE_OBJECT, self_py, "self");
            }
          GType actual_gtype = G_TYPE_FROM_INSTANCE ((GTypeInstance *)self_obj);
          if (plan->self_gtype != G_TYPE_INVALID && plan->self_gtype != G_TYPE_NONE
              && actual_gtype != 0 && !g_type_is_a (actual_gtype, plan->self_gtype))
            {
              return pygi_raise_gobject_type_error_for_gtype_named (plan->self_gtype, self_py, "self");
            }
          /* Transfer-full instance: the callee consumes the ref. Bump
           * before passing so the wrapper retains its own — without
           * this, regress_test_obj_instance_method_full on the same
           * wrapper twice in a row derefs a freed pointer.
           * Mirrors the PYGI_MARSHAL_GOBJECT_OWNED arg path. */
          if (plan->instance_transfer == GI_TRANSFER_EVERYTHING && G_IS_OBJECT (self_obj))
            g_object_ref ((GObject *)self_obj);
          self_ptr = self_obj;
          frame->bound_self = self_py;
        }
      frame->in_args[0].v_pointer = self_ptr;
    }

  for (size_t i = 0; i < plan->n_gi_args; i++)
    {
      const PyGIArgPlan *ap = &plan->args[i];

      /* If this slot is the user_data target of a callback param earlier
       * in the signature AND the caller supplied a Python value for it
       * (consumes_py_arg with a valid py_arg_index), stash that value
       * on the closure cookie. The inner-callback trampoline reads it
       * back when the C-side callback fires. Slots that ended up as
       * CLOSURE_DESTROY (caller omitted user_data) get None via the
       * dedicated branch below. */
      if (ap->owner_callback_arg >= 0 && ap->role == PYGI_ARG_ROLE_NORMAL && ap->consumes_py_arg
          && ap->py_arg_index >= 0 && (size_t)ap->py_arg_index < nargs)
        {
          /* pygi_callback_closure_new stashes the closure cookie at
           * cleanups[callback_arg].ptr regardless of scope (the
           * `kind` flag controls cleanup-time free; the ptr is the
           * back-link we use here to thread Python user_data). */
          const PyGIArgCleanup *cc = &frame->cleanups[ap->owner_callback_arg];
          if (cc->ptr != NULL)
            {
              PyObject *py = (PyObject *)(void *)(args[ap->py_arg_index]);
              pygi_callback_closure_set_py_user_data (cc->ptr, py);
              frame->in_args[ap->in_slot].v_pointer = cc->ptr;
              continue;
            }
        }

      /* -- Fast path for pre-resolved IN-arg shapes ----------------------- */
      if (G_LIKELY (ap->marshal_kind != PYGI_MARSHAL_GENERIC))
        {
          /* Bounds check: if the caller didn't supply enough positional
           * args fall through to the generic path which has the missing-
           * argument error machinery (and the nullable/optional handling). */
          if (G_UNLIKELY (ap->py_arg_index < 0 || (size_t)ap->py_arg_index >= nargs))
            goto generic_path;

          PyObject *py = (PyObject *)(void *)(args[ap->py_arg_index]);
          GIArgument *out = &frame->in_args[ap->in_slot];
          int64_t lv;
          double dv;
          switch (ap->marshal_kind)
            {
            case PYGI_MARSHAL_BOOL:
              {
                int b = PyObject_IsTrue (py);
                if (b < 0)
                  return -1;
                out->v_boolean = b ? TRUE : FALSE;
                continue;
              }
            case PYGI_MARSHAL_INT8:
              /* gchar args (e.g. add_main_option's short_name) are
               * tagged INT8 in GIR but pygobject-style callers pass
               * length-1 bytes/str - accept both. */
              if (PyBytes_Check (py) && PyBytes_GET_SIZE (py) == 1)
                {
                  out->v_int8 = (int8_t)((unsigned char)PyBytes_AS_STRING (py)[0]);
                  continue;
                }
              if (PyUnicode_Check (py) && PyUnicode_GetLength (py) == 1)
                {
                  out->v_int8 = (int8_t)(PyUnicode_ReadChar (py, 0) & 0xFF);
                  continue;
                }
              if (pygi_int8_from_py (py, out) != 0)
                return -1;
              continue;
            case PYGI_MARSHAL_UINT8:
              /* Same dual-shape acceptance as INT8 - guchar is
               * indistinguishable from gchar at the GIR layer. */
              if (PyBytes_Check (py) && PyBytes_GET_SIZE (py) == 1)
                {
                  out->v_uint8 = (uint8_t)((unsigned char)PyBytes_AS_STRING (py)[0]);
                  continue;
                }
              if (PyUnicode_Check (py) && PyUnicode_GetLength (py) == 1)
                {
                  out->v_uint8 = (uint8_t)(PyUnicode_ReadChar (py, 0) & 0xFF);
                  continue;
                }
              if (pygi_uint8_from_py (py, out) != 0)
                return -1;
              continue;
            case PYGI_MARSHAL_INT16:
              if (pygi_int16_from_py (py, out) != 0)
                return -1;
              continue;
            case PYGI_MARSHAL_UINT16:
              if (pygi_uint16_from_py (py, out) != 0)
                return -1;
              continue;
            case PYGI_MARSHAL_INT32:
              if (pygi_int32_from_py (py, out) != 0)
                return -1;
              continue;
            case PYGI_MARSHAL_ENUM_INT32:
              /* Read 64-bit: enum members are 32-bit but may be unsigned
                 (e.g. 1<<31), which overflows a signed 32-bit long on LLP64
                 (Windows). The defined-value check and the (int32_t) store
                 below collapse it back to the correct 32-bit slot. */
              lv = pygi_pyobj_to_longlong (py);
              if (lv == -1 && PyErr_Occurred ())
                return -1;
              /* Pygobject contract: an int outside the enum's defined
               * values is a TypeError, not a pass-through. Without
               * this check the bad value flows to a C function that
               * g_assert's on the unexpected slot. Flags can take any
               * bit combination so they're skipped (the FLAGS_UINT32
               * branch doesn't validate either). */
              {
                g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ap->cached_ti);
                if (iface != NULL && GI_IS_ENUM_INFO (iface) && !GI_IS_FLAGS_INFO (iface))
                  {
                    GIEnumInfo *enum_info = (GIEnumInfo *)iface;
                    unsigned int n_values = gi_enum_info_get_n_values (enum_info);
                    gboolean found = FALSE;
                    for (unsigned int ei = 0; ei < n_values; ei++)
                      {
                        g_autoptr (GIValueInfo) vi = gi_enum_info_get_value (enum_info, ei);
                        if (vi != NULL && gi_value_info_get_value (vi) == (int64_t)lv)
                          {
                            found = TRUE;
                            break;
                          }
                      }
                    if (!found)
                      {
                        PyErr_Format (PyExc_TypeError,
                                      "argument %zd: %lld is not a valid %s value",
                                      (Py_ssize_t)ap->py_arg_index + 1,
                                      (long long)lv,
                                      gi_base_info_get_name (iface));
                        return -1;
                      }
                  }
              }
              out->v_int32 = (int32_t)lv;
              continue;
            case PYGI_MARSHAL_UINT32:
            case PYGI_MARSHAL_FLAGS_UINT32:
              if (pygi_uint32_from_py (py, out) != 0)
                return -1;
              continue;
            case PYGI_MARSHAL_INT64:
              if (pygi_int64_from_py (py, out) != 0)
                return -1;
              continue;
            case PYGI_MARSHAL_UINT64:
              /* `K` format does its own type-check first and emits
               * "argument N must be int, not TYPE" rather than the int<I>
               * template. Match that, with PyGObject-style float->int
               * coercion as the same exception. */
              if (G_UNLIKELY (!PyLong_Check (py) && !PyFloat_Check (py) && !PyNumber_Check (py)))
                {
                  PyErr_Format (PyExc_TypeError,
                                "argument %zd must be int, not %s",
                                (Py_ssize_t)ap->py_arg_index + 1,
                                Py_TYPE (py)->tp_name);
                  return -1;
                }
              if (PyFloat_Check (py))
                {
                  out->v_uint64 = (uint64_t)(long long)PyFloat_AsDouble (py);
                  continue;
                }
              if (pygi_uint64_from_py (py, out) != 0)
                return -1;
              continue;
            case PYGI_MARSHAL_FLOAT:
              dv = PyFloat_AsDouble (py);
              if (dv == -1.0 && PyErr_Occurred ())
                return -1;
              out->v_float = (float)dv;
              continue;
            case PYGI_MARSHAL_DOUBLE:
              dv = PyFloat_AsDouble (py);
              if (dv == -1.0 && PyErr_Occurred ())
                return -1;
              out->v_double = dv;
              continue;
            case PYGI_MARSHAL_GTYPE:
              {
                GType gtype = G_TYPE_INVALID;
                if (pygi_gtype_from_py_object (py, &gtype) != 0)
                  return -1;
                out->v_size = (size_t)gtype;
                continue;
              }
            case PYGI_MARSHAL_GOBJECT:
              if (py == Py_None)
                {
                  /* pygobject historically accepts None for any GObject
                   * arg regardless of the GIR may-be-null annotation —
                   * several functions in introspected libs are
                   * mis-annotated but never deref. Don't reject here;
                   * the self-arg path (above) already covers the
                   * common crash shape (None as instance). */
                  out->v_pointer = NULL;
                  continue;
                }
              out->v_pointer = pygi_gobject_get (py);
              if (out->v_pointer == NULL)
                {
                  if (PyErr_ExceptionMatches (PyExc_AttributeError))
                    {
                      PyErr_Clear ();
                      return pygi_raise_gobject_type_error_for_gtype_named (
                          ap->type.gtype != G_TYPE_INVALID && ap->type.gtype != G_TYPE_NONE
                              ? ap->type.gtype
                              : G_TYPE_OBJECT,
                          py,
                          ap->cached_ai ? gi_base_info_get_name ((GIBaseInfo *)ap->cached_ai) : NULL);
                    }
                  return -1;
                }
              if (ap->type.gtype != G_TYPE_INVALID && ap->type.gtype != G_TYPE_NONE
                  && !g_type_is_a (G_TYPE_FROM_INSTANCE ((GTypeInstance *)out->v_pointer),
                                   ap->type.gtype))
                {
                  return pygi_raise_gobject_type_error_for_gtype_named (
                      ap->type.gtype, py,
                      ap->cached_ai ? gi_base_info_get_name ((GIBaseInfo *)ap->cached_ai) : NULL);
                }
              continue;
            case PYGI_MARSHAL_GOBJECT_OWNED:
              /* Transfer-full arg: callee will claim the supplied ref.
               * Our wrapper still holds its own ref, so we must bump
               * before passing - otherwise the wrapper's later dealloc
               * unrefs the same slot the callee owns, and the next
               * dispose on the callee's side hits a freed pointer.
               * Mirrors PYGI_MARSHAL_UTF8_OWNED (g_strdup before
               * passing). No cleanup is registered: on success the
               * callee owns the bumped ref; a bind-error after this
               * point leaks one ref (cleanup machinery runs the same
               * frees on success and failure, so we can't unref
               * conditionally - matches UTF8_OWNED's leak-on-error). */
              if (py == Py_None)
                {
                  out->v_pointer = NULL;
                  continue;
                }
              out->v_pointer = pygi_gobject_get (py);
              if (out->v_pointer == NULL)
                {
                  if (PyErr_ExceptionMatches (PyExc_AttributeError))
                    {
                      PyErr_Clear ();
                      return pygi_raise_gobject_type_error_for_gtype_named (
                          ap->type.gtype != G_TYPE_INVALID && ap->type.gtype != G_TYPE_NONE
                              ? ap->type.gtype
                              : G_TYPE_OBJECT,
                          py,
                          ap->cached_ai ? gi_base_info_get_name ((GIBaseInfo *)ap->cached_ai) : NULL);
                    }
                  return -1;
                }
              if (ap->type.gtype != G_TYPE_INVALID && ap->type.gtype != G_TYPE_NONE
                  && !g_type_is_a (G_TYPE_FROM_INSTANCE ((GTypeInstance *)out->v_pointer),
                                   ap->type.gtype))
                {
                  return pygi_raise_gobject_type_error_for_gtype_named (
                      ap->type.gtype, py,
                      ap->cached_ai ? gi_base_info_get_name ((GIBaseInfo *)ap->cached_ai) : NULL);
                }
              gpointer owned = NULL;
              if (pygi_instantiatable_ref (out->v_pointer, ap->type.gtype, &owned) != 0)
                return -1;
              out->v_pointer = owned;
              continue;
            case PYGI_MARSHAL_UTF8:
            case PYGI_MARSHAL_UTF8_OWNED:
              {
                PyObject *coerced_path = NULL;
                if (ap->tag == GI_TYPE_TAG_FILENAME && !PyUnicode_Check (py) && !PyBytes_Check (py)
                    && !PyByteArray_Check (py) && py != Py_None)
                  {
                    coerced_path = PyOS_FSPath (py);
                    if (coerced_path == NULL)
                      return -1;
                    py = coerced_path;
                  }
                if (py == Py_None)
                  {
                    Py_XDECREF (coerced_path);
                    if (ap->nullable_or_optional)
                      {
                        out->v_string = NULL;
                        continue;
                      }
                    PyErr_Format (PyExc_TypeError,
                                  "argument %zd must be str, bytes, or bytearray, not None",
                                  (Py_ssize_t)ap->py_arg_index + 1);
                    return -1;
                  }
                /* Accept str/bytes/bytearray - matches pygobject. */
                if (PyUnicode_Check (py))
                  {
#ifdef _WIN32
                    if (ap->tag == GI_TYPE_TAG_FILENAME)
                      {
                        /* Windows filenames are UTF-8 but may carry lone
                           surrogates from Windows paths; encode WTF-8 via
                           surrogatepass. Route the bytes through coerced_path
                           so the cleanup slot keeps it alive across the call. */
                        PyObject *enc
                            = PyUnicode_AsEncodedString (py, "utf-8", "surrogatepass");
                        if (enc == NULL)
                          {
                            Py_XDECREF (coerced_path);
                            return -1;
                          }
                        Py_XSETREF (coerced_path, enc);
                        out->v_string = PyBytes_AsString (enc);
                      }
                    else
                      out->v_string = (char *)PyUnicode_AsUTF8 (py);
#else
                    out->v_string = (char *)PyUnicode_AsUTF8 (py);
#endif
                  }
                else if (PyBytes_Check (py))
                  {
                    out->v_string = PyBytes_AsString (py);
                  }
                else if (PyByteArray_Check (py))
                  {
                    out->v_string = PyByteArray_AsString (py);
                  }
                else
                  {
                    Py_XDECREF (coerced_path);
                    PyErr_Format (PyExc_TypeError,
                                  "argument %zd must be str, bytes, or bytearray, not %s",
                                  (Py_ssize_t)ap->py_arg_index + 1,
                                  Py_TYPE (py)->tp_name);
                    return -1;
                  }
                if (out->v_string == NULL)
                  {
                    Py_XDECREF (coerced_path);
                    return -1;
                  }
                if (ap->marshal_kind == PYGI_MARSHAL_UTF8_OWNED)
                  {
                    char *dup = g_strdup (out->v_string);
                    if (dup == NULL)
                      {
                        Py_XDECREF (coerced_path);
                        PyErr_NoMemory ();
                        return -1;
                      }
                    out->v_string = dup;
                    Py_XDECREF (coerced_path);
                  }
                else if (coerced_path != NULL)
                  {
                    frame->cleanups[i].kind = PYGI_ARG_CLEANUP_PYOBJECT;
                    frame->cleanups[i].ptr = coerced_path;
                  }
                continue;
              }
            case PYGI_MARSHAL_GBYTES:
              {
                if (py == Py_None)
                  {
                    out->v_pointer = NULL;
                    continue;
                  }
                /* GLib.Bytes wrapper (the typical shape now that
                 * returns aren't auto-unwrapped to Python bytes):
                 * unwrap to the underlying GBytes and hand the callee
                 * a fresh ref. Wrapper retains its own ref via the
                 * boxed dealloc path. */
                {
                  gpointer boxed_ptr = NULL;
                  if (pygi_boxed_get (py, &boxed_ptr) == 0 && boxed_ptr != NULL)
                    {
                      out->v_pointer = g_bytes_ref ((GBytes *)boxed_ptr);
                      continue;
                    }
                  PyErr_Clear ();
                }
                Py_buffer *view = g_new (Py_buffer, 1);
                if (PyObject_GetBuffer (py, view, PyBUF_SIMPLE) != 0)
                  {
                    g_free (view);
                    return -1;
                  }
                GBytes *bytes = g_bytes_new_with_free_func (view->buf,
                                                            (gsize)view->len,
                                                            pygi_pybuffer_release_destroy_notify,
                                                            view);
                out->v_pointer = bytes;
                frame->cleanups[i].kind = PYGI_ARG_CLEANUP_GBYTES;
                frame->cleanups[i].ptr = bytes;
                continue;
              }
            case PYGI_MARSHAL_GENERIC:
              break; /* handled below */
            }
        }
    generic_path:;

      /* Borrowed - owned by the plan; no per-call allocate/unref. */
      GIArgInfo *ai = ap->cached_ai;
      GITypeInfo *ti = ap->cached_ti;

      /* -- closure/destroy companion: no Python arg consumed -- */
      if (ap->role == PYGI_ARG_ROLE_CLOSURE_DESTROY)
        {
          if (ap->owner_callback_arg >= 0)
            {
              const PyGIArgCleanup *cc = &frame->cleanups[ap->owner_callback_arg];
              frame->in_args[ap->in_slot].v_pointer = cc->ptr;
            }
          else if (ap->owner_callback_arg <= -2)
            {
              ssize_t callback_arg = -ap->owner_callback_arg - 2;
              const PyGIArgCleanup *cc = &frame->cleanups[callback_arg];
              GIArgInfo *callback_ai = plan->args[callback_arg].cached_ai;
              if (cc->ptr != NULL && gi_arg_info_get_scope (callback_ai) == GI_SCOPE_TYPE_NOTIFIED)
                frame->in_args[ap->in_slot].v_pointer = pygi_callback_closure_destroy;
              else
                frame->in_args[ap->in_slot].v_pointer = NULL;
            }
          else
            {
              frame->in_args[ap->in_slot].v_pointer = NULL;
            }
          /* Omitted user_data carries the callback closure cookie at the C
           * layer so a paired scope=notified destroy can release it. The
           * callback trampoline hides that cookie from Python unless explicit
           * Python user_data was supplied. */
          continue;
        }

      /* -- array length arg -- */
      if (ap->role == PYGI_ARG_ROLE_ARRAY_LENGTH)
        {
          const PyGIArgPlan *owner = &plan->args[ap->owner_array_arg];

          if (owner->length_kind == PYGI_LENGTH_AFTER_ARRAY)
            {
              /* IN/INOUT AFTER_ARRAY: both slots were assigned when the owner
               * array arg was processed - nothing to do here.
               * OUT AFTER_ARRAY: plan assigns an independent out_slot; set up
               * the storage so gi_function_info_invoke receives the right slot. */
              if (ap->direction == GI_DIRECTION_OUT)
                {
                  if (bind_out_storage (descriptor, frame, cb, plan, ap, ai, ti, i) == NULL)
                    return -1;
                }
              continue;
            }

          /* BEFORE_ARRAY: length precedes the array in the GI signature. */
          if (ap->direction == GI_DIRECTION_IN)
            {
              /* Record slot for back-fill when the array arg is processed. */
              frame->in_len_slot[i] = (size_t)ap->in_slot;
              frame->in_len_ti[i] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)ti);
              frame->in_args[ap->in_slot].v_uint64 = 0;
              continue;
            }

          if (ap->direction == GI_DIRECTION_INOUT)
            {
              /* defer_inout_length: set up OUT storage, put storage_ptr in in_args. */
              void *storage_ptr = bind_out_storage (descriptor, frame, cb, plan, ap, ai, ti, i);
              if (storage_ptr == NULL)
                return -1;
              /* sentinel (1) means caller_allocates - no in_args entry needed. */
              if (storage_ptr != (void *)(intptr_t)1)
                frame->in_args[ap->in_slot].v_pointer = storage_ptr;
              continue;
            }

          if (ap->direction == GI_DIRECTION_OUT)
            {
              /* Pure OUT length (BEFORE_ARRAY): set up its own out slot. */
              if (bind_out_storage (descriptor, frame, cb, plan, ap, ai, ti, i) == NULL)
                return -1;
              continue;
            }

          continue;
        }

      /* -- pure OUT -- */
      if (ap->direction == GI_DIRECTION_OUT)
        {
          if (bind_out_storage (descriptor, frame, cb, plan, ap, ai, ti, i) == NULL)
            return -1;
          continue;
        }

      /* -- INOUT -- */
      if (ap->direction == GI_DIRECTION_INOUT)
        {
          if (ap->caller_allocates)
            {
              /* Buffer pre-allocated; C fills it. No Python arg consumed. */
              if (bind_out_storage (descriptor, frame, cb, plan, ap, ai, ti, i) == NULL)
                return -1;
              continue;
            }

          /* INOUT C-array with length immediately following. */
          if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C
              && ap->length_kind == PYGI_LENGTH_AFTER_ARRAY)
            {
              ssize_t li = ap->length_arg;
              const PyGIArgPlan *lap = &plan->args[li];
              GITypeInfo *len_ti = plan->args[li].cached_ti;
              if (ap->array_elem_ti == NULL)
                {
                  pygi_unsupported_fallback_shape (descriptor->qualified_name,
                                                   cb,
                                                   "INOUT C-array missing element type");
                  return -1;
                }
              /* When the arg is optional and the caller omitted it,
               * substitute Py_None — without this guard the
               * args[py_arg_index] read below dereferences past the
               * supplied tuple and segfaults (e.g.
               * length_array_utf8_optional_inout() with no positional).
               * The downstream marshaller already handles None → NULL
               * for nullable arrays. */
              PyObject *array_arg;
              if (ap->py_arg_index >= 0 && (size_t)ap->py_arg_index < nargs)
                array_arg = args[ap->py_arg_index];
              else if (ap->nullable_or_optional)
                array_arg = Py_None;
              else
                {
                  PyErr_Format (PyExc_TypeError,
                                "%s() takes exactly %zu arguments (%zu given)",
                                pygi_bare_name (descriptor->qualified_name),
                                plan->n_py_args,
                                nargs);
                  return -1;
                }
              void *arr_storage
                  = gi_argument_storage_pointer (ap->storage_tag, &frame->out_values[ap->out_slot]);
              if (arr_storage == NULL)
                {
                  pygi_unsupported_fallback_shape (descriptor->qualified_name,
                                                   cb,
                                                   "INOUT C-array storage type");
                  return -1;
                }
              frame->out_tis[ap->out_slot] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)ti);
              frame->out_tis_count = (size_t)ap->out_slot + 1;
              frame->out_args[ap->out_slot].v_pointer = arr_storage;

              GIArgument tmp_len = { 0 };
              if (pygi_py_to_c_array_invoke (array_arg,
                                             ap->array_elem_ti,
                                             &frame->out_values[ap->out_slot],
                                             &tmp_len,
                                             len_ti,
                                             gi_type_info_is_zero_terminated (ti),
                                             0,
                                             &frame->cleanups[i],
                                             ap->transfer)
                  != 0)
                return -1;

              frame->out_tis[lap->out_slot] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)len_ti);
              frame->out_tis_count = (size_t)lap->out_slot + 1;
              frame->out_values[lap->out_slot] = tmp_len;
              void *len_storage = gi_argument_storage_pointer (lap->storage_tag,
                                                               &frame->out_values[lap->out_slot]);
              frame->out_args[lap->out_slot].v_pointer = len_storage;
              frame->in_args[ap->in_slot].v_pointer = arr_storage;
              frame->in_args[lap->in_slot].v_pointer = len_storage;
              continue;
            }

          /* INOUT C-array with length preceding (BEFORE_ARRAY). */
          if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C
              && ap->length_kind == PYGI_LENGTH_BEFORE_ARRAY)
            {
              ssize_t li = ap->length_arg;
              const PyGIArgPlan *lap = &plan->args[li];
              if (ap->array_elem_ti == NULL)
                {
                  pygi_unsupported_fallback_shape (descriptor->qualified_name,
                                                   cb,
                                                   "INOUT C-array (before-len) missing elem");
                  return -1;
                }
              /* See AFTER_ARRAY path: substitute Py_None for an omitted
               * optional arg so we don't read past the args[] tuple. */
              PyObject *array_arg;
              if (ap->py_arg_index >= 0 && (size_t)ap->py_arg_index < nargs)
                array_arg = args[ap->py_arg_index];
              else if (ap->nullable_or_optional)
                array_arg = Py_None;
              else
                {
                  PyErr_Format (PyExc_TypeError,
                                "%s() takes exactly %zu arguments (%zu given)",
                                pygi_bare_name (descriptor->qualified_name),
                                plan->n_py_args,
                                nargs);
                  return -1;
                }
              void *arr_storage
                  = gi_argument_storage_pointer (ap->storage_tag, &frame->out_values[ap->out_slot]);
              if (arr_storage == NULL)
                {
                  pygi_unsupported_fallback_shape (descriptor->qualified_name,
                                                   cb,
                                                   "INOUT C-array (before-len) storage type");
                  return -1;
                }
              frame->out_tis[ap->out_slot] = (GITypeInfo *)gi_base_info_ref ((GIBaseInfo *)ti);
              frame->out_tis_count = (size_t)ap->out_slot + 1;
              frame->out_args[ap->out_slot].v_pointer = arr_storage;

              GITypeInfo *len_ti = plan->args[li].cached_ti;
              GIArgument tmp_len = { 0 };
              if (pygi_py_to_c_array_invoke (array_arg,
                                             ap->array_elem_ti,
                                             &frame->out_values[ap->out_slot],
                                             &tmp_len,
                                             len_ti,
                                             gi_type_info_is_zero_terminated (ti),
                                             0,
                                             &frame->cleanups[i],
                                             ap->transfer)
                  != 0)
                return -1;

              /* Back-fill the deferred INOUT length out slot. */
              frame->out_values[lap->out_slot] = tmp_len;
              frame->in_args[ap->in_slot].v_pointer = arr_storage;
              continue;
            }

          /* Generic INOUT (scalar, interface, GArray/GList/GHash/GValue/GVariant,
           * C-array with fixed-size or zero-terminated length). */
          {
            void *storage_ptr = bind_out_storage (descriptor, frame, cb, plan, ap, ai, ti, i);
            if (storage_ptr == NULL)
              return -1;
            if (storage_ptr == (void *)(intptr_t)1)
              continue; /* caller_allocates - already handled */
            if (ap->py_arg_index < 0 || (size_t)ap->py_arg_index >= nargs)
              {
                if (ap->nullable_or_optional)
                  {
                    frame->in_args[ap->in_slot].v_pointer = NULL;
                    continue;
                  }
                PyErr_Format (PyExc_TypeError,
                              "%s() takes exactly %zu arguments (%zu given)",
                              pygi_bare_name (descriptor->qualified_name),
                              plan->n_py_args,
                              nargs);
                return -1;
              }
            if (bind_inout_value (frame, ap, ai, args[ap->py_arg_index], i) != 0)
              return -1;
            continue;
          }
        }

      /* -- IN arg -- */

      /* IN C-array, length immediately following. */
      if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C
          && ap->length_kind == PYGI_LENGTH_AFTER_ARRAY)
        {
          ssize_t li = ap->length_arg;
          const PyGIArgPlan *lap = &plan->args[li];
          GITypeInfo *len_ti = plan->args[li].cached_ti;
          if (ap->array_elem_ti == NULL)
            {
              pygi_unsupported_fallback_shape (descriptor->qualified_name,
                                               cb,
                                               "IN C-array missing element type");
              return -1;
            }
          if (ap->py_arg_index < 0 || (size_t)ap->py_arg_index >= nargs)
            {
              PyErr_SetString (PyExc_TypeError, "missing sequence argument");
              return -1;
            }
          if (pygi_py_to_c_array_invoke (args[ap->py_arg_index],
                                         ap->array_elem_ti,
                                         &frame->in_args[ap->in_slot],
                                         &frame->in_args[lap->in_slot],
                                         len_ti,
                                         gi_type_info_is_zero_terminated (ti),
                                         0,
                                         &frame->cleanups[i],
                                         ap->transfer)
              != 0)
            return -1;
          continue;
        }

      /* IN C-array, length preceding (BEFORE_ARRAY). */
      if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C
          && ap->length_kind == PYGI_LENGTH_BEFORE_ARRAY)
        {
          ssize_t li = ap->length_arg;
          if (ap->array_elem_ti == NULL)
            {
              pygi_unsupported_fallback_shape (descriptor->qualified_name,
                                               cb,
                                               "IN C-array (before-len) missing element type");
              return -1;
            }
          if (ap->py_arg_index < 0 || (size_t)ap->py_arg_index >= nargs)
            {
              PyErr_SetString (PyExc_TypeError, "missing sequence argument");
              return -1;
            }
          GIArgument tmp_len = { 0 };
          if (pygi_py_to_c_array_invoke (args[ap->py_arg_index],
                                         ap->array_elem_ti,
                                         &frame->in_args[ap->in_slot],
                                         &tmp_len,
                                         frame->in_len_ti[li],
                                         gi_type_info_is_zero_terminated (ti),
                                         0,
                                         &frame->cleanups[i],
                                         ap->transfer)
              != 0)
            return -1;
          frame->in_args[frame->in_len_slot[li]] = tmp_len;
          continue;
        }

      /* IN arg: GArray, GHash, GList, GSList, GValue, GVariant, callback,
       * C-array (fixed/zt), or generic scalar/interface. */
      if (ap->py_arg_index < 0 || (size_t)ap->py_arg_index >= nargs)
        {
          if (ap->nullable_or_optional)
            {
              frame->in_args[ap->in_slot].v_pointer = NULL;
              continue;
            }
          PyErr_Format (PyExc_TypeError,
                        "%s() takes exactly %zu arguments (%zu given)",
                        pygi_bare_name (descriptor->qualified_name),
                        plan->n_py_args,
                        nargs);
          return -1;
        }
      {
        PyGIMarshalSlot mslot = {
          .type = ti,
          .pygi_type = &ap->type,
          .transfer = ap->transfer,
          .kind = PYGI_MARSHAL_TARGET_GIARG,
          .target.giarg = &frame->in_args[ap->in_slot],
          .cleanup = &frame->cleanups[i],
          .arg_info = ai,
          .arg_pos = (int)(ap->py_arg_index + 1),
        };
        if (ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C
            && ap->length_arg >= 0)
          {
            size_t li = (size_t)ap->length_arg;
            const PyGIArgPlan *lap = &plan->args[li];
            if (lap->in_slot >= 0)
              {
                mslot.length_type = lap->cached_ti;
                mslot.length_arg = &frame->in_args[lap->in_slot];
              }
          }
        /* Some marshalers silently treat None as an empty/NULL
         * container. Reject the shapes known to crash when the slot is
         * not nullable_or_optional. Length-paired C arrays have
         * dedicated paths above; fixed-size and zero-terminated arrays
         * are routed here. Fixed arrays whose element type is
         * pointer-shaped can still accept NULL even when the metadata
         * does not mark them nullable. */
        if (args[ap->py_arg_index] == Py_None && !ap->nullable_or_optional
            && ((ap->tag == GI_TYPE_TAG_ARRAY && ap->array_type == GI_ARRAY_TYPE_C
                 && ap->array_has_fixed_size && ap->array_fixed_size > 0
                 && ap->array_elem_ti != NULL && !gi_type_info_is_pointer (ap->array_elem_ti))
                || ap->tag == GI_TYPE_TAG_GHASH || ap->tag == GI_TYPE_TAG_GLIST
                || ap->tag == GI_TYPE_TAG_GSLIST))
          {
            PyErr_Format (PyExc_TypeError,
                          "argument %zd: a container is required, not None",
                          (Py_ssize_t)ap->py_arg_index + 1);
            return -1;
          }
        if (pygi_marshal_from_py (args[ap->py_arg_index], &mslot) != 0)
          {
            if (ap->cached_ai != NULL && PyErr_Occurred () == PyExc_TypeError)
              {
                PyObject *exc = PyErr_GetRaisedException ();
                const char *aname = gi_base_info_get_name ((GIBaseInfo *)ap->cached_ai);
                if (aname != NULL)
                  PyErr_Format (PyExc_TypeError, "%s: %S", aname, exc);
                else
                  PyErr_SetRaisedException (exc);
                Py_DECREF (exc);
              }
            return -1;
          }
        if (gi_type_info_is_gvalue (ti) && !gi_type_info_is_pointer (ti))
          {
            /* By-value GValue inputs can be shallow-copied by callees into
             * returned containers. If we unset the input copy unconditionally
             * after the call, we double-free shared payloads like strings. */
            frame->cleanups[i].kind = PYGI_ARG_CLEANUP_NONE;
            frame->cleanups[i].ptr = NULL;
          }
      }
    }

  if (nargs > plan->n_py_args)
    {
      PyErr_Format (PyExc_TypeError,
                    "%s() takes exactly %zu arguments (%zu given)",
                    pygi_bare_name (descriptor->qualified_name),
                    plan->n_py_args,
                    nargs);
      return -1;
    }

  return 0;
}
