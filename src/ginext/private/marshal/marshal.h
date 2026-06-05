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

/* marshal.h - GIArgument <-> PyObject * dispatch for all GI type tags. */
#pragma once

#include <Python.h>
#include <girepository/girepository.h>
#include <glib-object.h>
#include <stdbool.h>
#include "marshal/pygi-value.h"
#include "invoke/arg-cleanup.h"

/* -----------------------------------------------------------------------
 * Unified marshalling entry - see todo-2026-05-10.md "Marshalling
 * unification".  PyGIMarshalSlot collects everything a single conversion
 * needs to know: target shape (GIArgument, raw memory, or GValue),
 * transfer semantics, optional length pairing, optional cleanup tracking.
 * Phase 1: surface only - internally these adapters call the legacy
 * dispatchers below.  Later phases migrate consumers (invoke/bind,
 * invoke/return, closure, gvalue) onto pygi_marshal_from_py / to_py.
 * --------------------------------------------------------------------- */

typedef enum
{
  PYGI_MARSHAL_TARGET_GIARG, /* GIArgument*  (FFI/JIT call slots) */
  PYGI_MARSHAL_TARGET_MEMORY, /* raw bytes    (struct fields, C-array elements) */
  PYGI_MARSHAL_TARGET_GVALUE, /* GValue*      (props, signals, GValue arrays) */
} PyGIMarshalTargetKind;

typedef struct
{
  GITypeInfo *type;
  const PyGIType *pygi_type;
  GITransfer transfer;
  /* When true, marshal_to_py uses `transfer` above instead of deriving
   * it from `callable`. Required for callback inbound args: the
   * callable's `caller_owns` is the RETURN-VALUE transfer, but we're
   * marshalling individual parameters here - leaking that across to
   * e.g. a transfer-none `const char*` parameter triggers a double
   * free when the marshaller g_free's the inbound buffer the C
   * caller still owns. Trampolines set this true and supply each
   * arg's real transfer via gi_arg_info_get_ownership_transfer. */
  bool transfer_set;

  PyGIMarshalTargetKind kind;
  union
  {
    GIArgument *giarg;
    void *memory;
    GValue *gvalue;
  } target;

  /* Optional. Set when type is a length-paired C array. */
  GITypeInfo *length_type;
  GIArgument *length_arg;

  /* Optional. Caller-allocated out buffer flag. */
  bool caller_allocates;

  /* Optional. Cleanup record to populate (from_py only). */
  PyGIArgCleanup *cleanup;

  /* Optional. Callable info, used for transfer semantics on returns. */
  GICallableInfo *callable;

  /* Optional. Argument info - needed for callback-scope and a couple of
   * marshallers that want to walk back to the (param,name,direction) tuple. */
  GIArgInfo *arg_info;

  /* Optional. 1-based Python arg position for type-check errors; 0 to skip. */
  int arg_pos;
} PyGIMarshalSlot;

/* Python value -> C representation specified by `slot`.
 * Returns 0 on success, -1 with a Python exception set on failure. */
int
pygi_marshal_from_py (PyObject *value, PyGIMarshalSlot *slot);

/* C representation specified by `slot` -> new Python reference, or NULL on
 * error (with a Python exception set). */
PyObject *
pygi_marshal_to_py (const PyGIMarshalSlot *slot);

void
pygi_set_unimplemented_type_error (const char *what, GITypeInfo *ti, const char *detail);

/* Type-check h against the expected GI type tag for user-visible argument
 * arg_index (1-based). Raises TypeError "argument N must be TYPE, not TYPE"
 * and returns -1 on mismatch; returns 0 on success or for unhandled tags. */
int
pygi_check_arg_type (PyObject *h, GITypeTag tag, int arg_index);

int
pygi_argument_from_py (PyObject *h, GITypeInfo *ti, GIArgument *out);

PyObject *
pygi_argument_to_py (GICallableInfo *cb, GITypeInfo *ti, GIArgument *arg);

/* Same as pygi_argument_to_py but with an explicit transfer; bypasses
 * the gi_callable_info_get_caller_owns lookup so callers marshalling
 * per-argument data (callback inbound args, GValue array elements, ...)
 * can specify the parameter's own transfer instead of inheriting the
 * callable's return-value transfer. */
PyObject *
pygi_argument_to_py_transfer (GICallableInfo *cb,
                              GITypeInfo *ti,
                              GIArgument *arg,
                              GITransfer transfer);

/* Marshal one Python value to a GIArgument for an IN or INOUT call parameter.
 * Handles GArray, GHash, GList, GSList, GValue, GVariant, callback, C-array
 * (fixed-size / zero-terminated only - length-paired C-arrays are handled by
 * the binder), and generic scalar/interface via pygi_argument_from_py.
 * arg_pos: 1-based Python argument position for error messages; pass 0 to
 * skip the pygi_check_arg_type pre-check (INOUT path).
 * Returns 0 on success, -1 with a Python exception set on failure. */
int
pygi_argument_from_py_for_call (GITypeTag tag,
                                GIArrayType array_type,
                                GITransfer transfer,
                                GITypeInfo *ti,
                                GIArgInfo *ai,
                                PyObject *pyval,
                                GIArgument *dest,
                                PyGIArgCleanup *cleanup,
                                int arg_pos);
