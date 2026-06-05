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

#pragma once

/* Descriptor-time callable analysis: interprets GICallableInfo once and
 * produces explicit per-argument and per-out-slot metadata consumed by
 * invoke-bind.c and invoke-return.c. */

#include <girepository/girepository.h>
#include <stdbool.h>
#include <stddef.h>
#include <sys/types.h>

#include "marshal/pygi-value.h"

typedef enum
{
  PYGI_ARG_ROLE_NORMAL = 0,
  PYGI_ARG_ROLE_CLOSURE_DESTROY, /* filled with NULL, no Python arg consumed */
  PYGI_ARG_ROLE_ARRAY_LENGTH, /* value derived or handled by owner array */
} PyGIArgRole;

typedef enum
{
  PYGI_LENGTH_NONE = 0, /* no length metadata (GArray/GPtrArray/etc.) */
  PYGI_LENGTH_BEFORE_ARRAY, /* length GI arg index < array GI arg index */
  PYGI_LENGTH_AFTER_ARRAY, /* length GI arg is arg immediately following array */
  PYGI_LENGTH_FIXED, /* fixed-size C array, no length arg */
  PYGI_LENGTH_ZERO_TERMINATED, /* zero-terminated C array, no length arg */
} PyGILengthKind;

/* Pre-resolved Python->C marshal kind for an IN argument. Set at plan-
 * build time so the binder can dispatch with a single small switch
 * instead of walking the GIR tag tree on every call.
 *
 * GENERIC means "anything we couldn't pre-resolve" - the binder falls
 * back to pygi_argument_from_py_for_call for those, which is the path
 * arrays / lists / hashes / GValues / callbacks / structs go through. */
typedef enum
{
  PYGI_MARSHAL_GENERIC = 0,
  PYGI_MARSHAL_BOOL,
  PYGI_MARSHAL_INT8,
  PYGI_MARSHAL_UINT8,
  PYGI_MARSHAL_INT16,
  PYGI_MARSHAL_UINT16,
  PYGI_MARSHAL_INT32,
  PYGI_MARSHAL_UINT32,
  PYGI_MARSHAL_INT64,
  PYGI_MARSHAL_UINT64,
  PYGI_MARSHAL_FLOAT,
  PYGI_MARSHAL_DOUBLE,
  PYGI_MARSHAL_GOBJECT,
  PYGI_MARSHAL_GOBJECT_OWNED, /* GObject*, g_object_ref'd - for TRANSFER_EVERYTHING */
  PYGI_MARSHAL_GBYTES,
  PYGI_MARSHAL_UTF8,
  PYGI_MARSHAL_UTF8_OWNED,
  PYGI_MARSHAL_GTYPE,
  PYGI_MARSHAL_ENUM_INT32,
  PYGI_MARSHAL_FLAGS_UINT32,
} PyGIMarshalKind;

typedef struct
{
  guint gi_index;
  GIDirection direction;
  GITransfer transfer;
  GITypeTag tag;
  GIArrayType array_type; /* valid only when tag == GI_TYPE_TAG_ARRAY */
  GITypeTag storage_tag;
  PyGIType type;

  PyGIArgRole role;
  bool consumes_py_arg;
  bool nullable_or_optional;
  bool caller_allocates;

  ssize_t py_arg_index; /* index into Python args[]; -1 for hidden/derived */
  ssize_t in_slot; /* index into in_args[]; -1 if not in in_args */
  ssize_t out_slot; /* index into out_args[]/out_values[]; -1 if none */

  ssize_t length_arg; /* array: GI arg index of the length arg; -1 if none */
  ssize_t owner_array_arg; /* length: GI arg index of the owning array; -1 if none */
  ssize_t owner_callback_arg; /* user_data slot: GI arg index of the owning
                                 callback param, so bind.c can find that
                                 callback's closure cookie and stash the
                                 user-supplied py_user_data on it. Destroy
                                 notify slots use -2 - callback_arg, keeping
                                 them negative for un-elide logic while still
                                 carrying the owner callback index. -1 for
                                 unrelated slots. */
  PyGILengthKind length_kind; /* array: how the length is provided */

  /* Cached GI metadata, owned by the plan. Filled at descriptor build
   * time so bind/return can avoid the per-call gi_callable_info_get_arg
   * + gi_arg_info_get_type_info refcount churn (each call was burning
   * ~1.2% of the hot loop in gi_base_info_unref alone). */
  GIArgInfo *cached_ai;
  GITypeInfo *cached_ti;
  GITypeInfo *array_elem_ti;
  GITypeTag array_elem_tag;
  gsize array_elem_size;
  size_t array_fixed_size;
  bool array_has_fixed_size;
  bool caller_allocates_gvalue;
  gsize caller_allocates_size;

  /* Pre-resolved marshal dispatch kind for IN args; GENERIC for
   * anything that still needs the slow tag-tree walk. */
  PyGIMarshalKind marshal_kind;
} PyGIArgPlan;

typedef struct
{
  guint gi_arg_index; /* which GI arg this OUT slot corresponds to */
  bool visible; /* shows up in the Python return value */
  bool consumed_by_array; /* absorbed as an array length, not returned */
  bool caller_allocates; /* OUT arg has (caller-allocates); marshal-to-py
                                   * needs to take ownership of the bind.c-
                                   * allocated buffer (no extra copy needed).
                                   * Without this, the buffer is freed in the
                                   * cleanup pass while the wrapper still
                                   * holds the pointer -> dangle / crash. */
  ssize_t paired_length_out_slot; /* for OUT array: which out slot is the length; -1 */
  ssize_t paired_length_in_slot; /* for OUT array with IN-only length: the in slot */
  ssize_t paired_in_length_gi_arg; /* GI arg index of the IN-only length; -1 */
  GITypeTag tag;
  GIArrayType array_type;
  const char *arg_name; /* borrowed from the plan's cached GIArgInfo */
} PyGIOutSlotPlan;

typedef struct
{
  GICallableInfo *callable; /* borrowed from descriptor */
  bool has_self;
  /* Expected instance GType for has_self methods (looked up from the
   * callable's container at plan time). bind.c uses this to reject a
   * self argument whose runtime GType isn't compatible — without it
   * the wrong-type pointer flows straight to the C method and trips a
   * g_return_if_fail / member-access crash. G_TYPE_INVALID for
   * functions, static methods, or callables whose container can't
   * resolve to a registered type. */
  GType self_gtype;
  /* Ownership transfer for the instance/self argument
   * (gi_callable_info_get_instance_ownership_transfer). When this is
   * GI_TRANSFER_EVERYTHING the callee consumes the caller's ref; the
   * Python wrapper still holds its own ref, so bind.c must
   * g_object_ref the instance before passing — otherwise a second
   * call on the same wrapper dereferences a freed object
   * (regress_test_obj_instance_method_full does this). */
  GITransfer instance_transfer;
  size_t n_gi_args;
  size_t n_py_args; /* expected Python positional arg count */
  size_t n_in_args; /* in_args[] slots used (= frame.in_index after bind) */
  size_t n_out_args; /* out_args[] slots used (= frame.out_index after bind) */
  PyGIType return_type;
  GITypeInfo *return_ti; /* owned */
  GITypeTag return_tag;
  GIArrayType return_array_type;
  ssize_t return_array_length_arg;
  GITransfer return_transfer;
  bool return_null_is_error;
  bool can_throw_gerror;

  /* Caller-allocated, each n_gi_args elements, zero-initialised before call. */
  PyGIArgPlan *args;
  /* Caller-allocated, n_gi_args elements (upper bound for n_out_args). */
  PyGIOutSlotPlan *out_slots;
} PyGIInvokePlan;

/* Fill plan from cb. Both args[] and out_slots[] must be caller-allocated
 * with at least n_gi_args elements and zero-initialised before the call.
 * has_self: 1 for bound methods. nargs: Python positional arg count (used to
 * validate closure/destroy arity detection).
 *
 * After calling this, plan->args[i].cached_ai/cached_ti hold owning refs
 * - release them with pygi_invoke_plan_clear when done. */
void
pygi_invoke_plan (GICallableInfo *cb, int has_self, size_t nargs, PyGIInvokePlan *plan);

/* Release the cached_ai/cached_ti owned by each plan->args[i]. Safe to
 * call on a zero-initialised or already-cleared plan. */
void
pygi_invoke_plan_clear (PyGIInvokePlan *plan);
