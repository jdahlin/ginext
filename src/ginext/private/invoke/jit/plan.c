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

#include <girepository/girepository.h>
#include <girepository/girffi.h>
/* invoke/jit/plan.c - descriptor-time JIT lowering for direct-call shapes.
 *
 * This file does two things on every descriptor build:
 *
 *   1. Build the shared PyGIInvokePlan (per-arg metadata, in/out slot
 *      assignment, length pairing). The same plan drives the FFI binder
 *      and shaper at runtime, so here we just compute it once and cache
 *      it inside PyGICompiledCallable.
 *
 *   2. Lower the plan to a PyGIJitPlan: an ABI-level view of the
 *      callable's argument list. The x86_64 backend reads only the
 *      PyGIJitPlan and the prepared PyGIInvokeFrame; it does not look
 *      at GI metadata.
 *
 * If lowering rejects the callable, we fall back to the legacy narrow
 * PyGISignature builder; if that also rejects, descriptor build fails
 * and the descriptor uses FFI invoke.
 */
#include "invoke/jit/plan.h"

#include "invoke/jit/invoke.h"
#include "jit/jit.h"
#include "runtime/module_funcs.h"
#include "runtime/stats.h"

#include <dlfcn.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern PyGIJittedTrampoline
pygi_jit_emit_full_x86_64 (PyGICompiledCallable *compiled, const char *name);

typedef struct
{
  bool has_jit_kind;
  PyGIJitTypeKind jit_kind;
  bool has_return_abi;
  PyGIAbiKind return_abi;
} PyGIJitTagShape;

/**
 * jit_tag_shape_from_gi_tag:
 * @tag: raw GI type tag to classify
 * @out: shape record populated on success
 *
 * Maps tag-only scalar and pointer-like GI types to the two JIT planning
 * axes: narrow-signature type and C ABI return kind. Interface tags are
 * resolved by callers because they need GIBaseInfo metadata.
 */
static int
jit_tag_shape_from_gi_tag (GITypeTag tag, PyGIJitTagShape *out)
{
  g_return_val_if_fail (out != NULL, -1);

  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_VOID,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_VOID,
      };
      return 0;
    case GI_TYPE_TAG_BOOLEAN:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_BOOL,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_I32,
      };
      return 0;
    case GI_TYPE_TAG_INT8:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_INT8,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_I8,
      };
      return 0;
    case GI_TYPE_TAG_UINT8:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_UINT8,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_U8,
      };
      return 0;
    case GI_TYPE_TAG_INT16:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_INT16,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_I16,
      };
      return 0;
    case GI_TYPE_TAG_UINT16:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_UINT16,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_U16,
      };
      return 0;
    case GI_TYPE_TAG_INT32:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_INT32,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_I32,
      };
      return 0;
    case GI_TYPE_TAG_UINT32:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_UINT32,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_U32,
      };
      return 0;
    case GI_TYPE_TAG_INT64:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_INT64,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_I64,
      };
      return 0;
    case GI_TYPE_TAG_UINT64:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_UINT64,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_U64,
      };
      return 0;
    case GI_TYPE_TAG_FLOAT:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_FLOAT,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_FLOAT,
      };
      return 0;
    case GI_TYPE_TAG_DOUBLE:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_DOUBLE,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_DOUBLE,
      };
      return 0;
    case GI_TYPE_TAG_UNICHAR:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_UNICHAR,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_I32,
      };
      return 0;
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_UTF8,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_POINTER,
      };
      return 0;
    case GI_TYPE_TAG_GTYPE:
      *out = (PyGIJitTagShape){
        .has_jit_kind = true,
        .jit_kind = PYGI_TY_UINT64,
        .has_return_abi = true,
        .return_abi = PYGI_ABI_U64,
      };
      return 0;
    case GI_TYPE_TAG_ARRAY:
    case GI_TYPE_TAG_GLIST:
    case GI_TYPE_TAG_GSLIST:
    case GI_TYPE_TAG_GHASH:
    case GI_TYPE_TAG_ERROR:
      *out = (PyGIJitTagShape){
        .has_return_abi = true,
        .return_abi = PYGI_ABI_POINTER,
      };
      return 0;
    case GI_TYPE_TAG_INTERFACE:
    default:
      return -1;
    }
}

static int
pygi_jit_type_kind_from_gi (GITypeInfo *ti, PyGIJitTypeKind *out)
{
  GITypeTag tag = gi_type_info_get_tag (ti);
  if (tag != GI_TYPE_TAG_INTERFACE)
    {
      PyGIJitTagShape shape = { 0 };
      if (jit_tag_shape_from_gi_tag (tag, &shape) != 0 || !shape.has_jit_kind)
        return -1;
      *out = shape.jit_kind;
      return 0;
    }

  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL)
    return -1;
  if (gi_type_info_is_param_spec (ti))
    return -1;
  if (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface))
    {
      *out = PYGI_TY_GOBJECT;
      return 0;
    }
  if (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface))
    {
      *out = PYGI_TY_INT32;
      return 0;
    }
  return -1;
}

/**
 * abi_kind_for_interface_return:
 * @ti: GI metadata for an interface return type
 * @out: ABI return kind populated on success
 *
 * Resolves interface return values that need GIBaseInfo metadata. Object,
 * boxed, callback, and interface-like returns are pointers; enum and flags
 * returns use their integer storage ABI.
 */
static int
abi_kind_for_interface_return (GITypeInfo *ti, PyGIAbiKind *out)
{
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
  if (iface == NULL)
    return -1;
  if (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface) || GI_IS_STRUCT_INFO (iface)
      || GI_IS_UNION_INFO (iface) || GI_IS_CALLBACK_INFO (iface))
    {
      *out = PYGI_ABI_POINTER;
      return 0;
    }
  if (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface))
    {
      *out = PYGI_ABI_I32;
      return 0;
    }
  return -1;
}

/* Map a GI return type tag to the ABI return kind. Returns -1 if the
 * caller should reject the callable. */
static int
abi_kind_for_return (GITypeInfo *ti, PyGIAbiKind *out)
{
  GITypeTag tag = gi_type_info_get_tag (ti);
  if (tag == GI_TYPE_TAG_INTERFACE)
    return abi_kind_for_interface_return (ti, out);

  PyGIJitTagShape shape = { 0 };
  if (jit_tag_shape_from_gi_tag (tag, &shape) != 0 || !shape.has_return_abi)
    return -1;

  *out = shape.return_abi;
  return 0;
}

static int
can_direct_scalar_out (PyGIJitTypeKind kind)
{
  switch (kind)
    {
    case PYGI_TY_BOOL:
    case PYGI_TY_INT8:
    case PYGI_TY_UINT8:
    case PYGI_TY_INT16:
    case PYGI_TY_UINT16:
    case PYGI_TY_INT32:
    case PYGI_TY_UINT32:
    case PYGI_TY_UNICHAR:
    case PYGI_TY_INT64:
    case PYGI_TY_UINT64:
    case PYGI_TY_FLOAT:
    case PYGI_TY_DOUBLE:
      return 1;
    case PYGI_TY_VOID:
    case PYGI_TY_UTF8:
    case PYGI_TY_UTF8_OWNED:
    case PYGI_TY_STRV:
    case PYGI_TY_GOBJECT:
    case PYGI_TY_GOBJECT_OWNED:
      return 0;
    }
  return 0;
}

static int
narrow_signature_from_callable (GICallableInfo *cb, int has_self, PyGISignature *out)
{
  int n_args = (int)gi_callable_info_get_n_args (cb);
  if (n_args > PYGI_MAX_ARGS - (has_self ? 1 : 0))
    return -1;

  g_autoptr (GITypeInfo) ret_ti = gi_callable_info_get_return_type (cb);
  GITypeTag ret_tag = gi_type_info_get_tag (ret_ti);
  if (pygi_jit_type_kind_from_gi (ret_ti, &out->ret) != 0)
    return -1;

  /* The JIT's gobject return helper assumes transfer=EVERYTHING (it claims
   * the caller's ref instead of bumping). Bail back to FFI for getters /
   * borrowed-ref returns so we don't dangle. */
  if (out->ret == PYGI_TY_GOBJECT
      && gi_callable_info_get_caller_owns (cb) != GI_TRANSFER_EVERYTHING)
    return -1;

  out->has_self = has_self;
  out->n_out_args = 0;
  out->flags = 0;
  if (gi_callable_info_can_throw_gerror (cb))
    {
      if (!has_self && ret_tag == GI_TYPE_TAG_VOID && n_args == 0)
        {
          out->n_args = 0;
          out->flags |= PYGI_SIG_THROWS_GERROR;
          return 0;
        }
      if (!has_self && ret_tag == GI_TYPE_TAG_BOOLEAN && n_args == 1)
        {
          g_autoptr (GIArgInfo) ai = gi_callable_info_get_arg (cb, 0);
          if (gi_arg_info_get_direction (ai) == GI_DIRECTION_IN)
            {
              g_autoptr (GITypeInfo) ti = gi_arg_info_get_type_info (ai);
              PyGIJitTypeKind arg_kind;
              if (pygi_jit_type_kind_from_gi (ti, &arg_kind) == 0 && arg_kind != PYGI_TY_FLOAT
                  && arg_kind != PYGI_TY_DOUBLE)
                {
                  out->n_args = 1;
                  out->args[0] = arg_kind;
                  out->flags |= PYGI_SIG_THROWS_GERROR;
                  return 0;
                }
            }
        }
      return -1;
    }
  switch (ret_tag)
    {
    case GI_TYPE_TAG_INT8:
      out->flags |= PYGI_SIG_RET_WIDEN_S8;
      break;
    case GI_TYPE_TAG_UINT8:
    case GI_TYPE_TAG_BOOLEAN:
      out->flags |= PYGI_SIG_RET_WIDEN_U8;
      break;
    case GI_TYPE_TAG_INT16:
      out->flags |= PYGI_SIG_RET_WIDEN_S16;
      break;
    case GI_TYPE_TAG_UINT16:
      out->flags |= PYGI_SIG_RET_WIDEN_U16;
      break;
    default:
      break;
    }

  if (!has_self && (ret_tag == GI_TYPE_TAG_VOID || ret_tag == GI_TYPE_TAG_BOOLEAN) && n_args == 1)
    {
      g_autoptr (GIArgInfo) ai = gi_callable_info_get_arg (cb, 0);
      GIDirection dir = gi_arg_info_get_direction (ai);
      if ((dir == GI_DIRECTION_OUT || (dir == GI_DIRECTION_INOUT && ret_tag == GI_TYPE_TAG_VOID))
          && !gi_arg_info_is_caller_allocates (ai))
        {
          g_autoptr (GITypeInfo) ti = gi_arg_info_get_type_info (ai);
          PyGIJitTypeKind out_kind;
          if (pygi_jit_type_kind_from_gi (ti, &out_kind) == 0 && can_direct_scalar_out (out_kind))
            {
              out->n_args = dir == GI_DIRECTION_INOUT ? 1 : 0;
              out->n_out_args = 1;
              if (dir == GI_DIRECTION_INOUT)
                out->args[0] = out_kind;
              out->out_args[0] = out_kind;
              return 0;
            }
        }
    }

  if (has_self && n_args == 2)
    {
      g_autoptr (GIArgInfo) len_ai = gi_callable_info_get_arg (cb, 0);
      g_autoptr (GIArgInfo) arr_ai = gi_callable_info_get_arg (cb, 1);
      g_autoptr (GITypeInfo) len_ti = gi_arg_info_get_type_info (len_ai);
      g_autoptr (GITypeInfo) arr_ti = gi_arg_info_get_type_info (arr_ai);
      unsigned int len_index = 0;

      if (gi_arg_info_get_direction (len_ai) == GI_DIRECTION_IN
          && gi_arg_info_get_direction (arr_ai) == GI_DIRECTION_IN
          && pygi_jit_type_kind_from_gi (len_ti, &out->args[0]) == 0
          && out->args[0] == PYGI_TY_INT32 && gi_type_info_get_tag (arr_ti) == GI_TYPE_TAG_ARRAY
          && gi_type_info_get_array_length_index (arr_ti, &len_index) && len_index == 0)
        {
          g_autoptr (GITypeInfo) elem_ti = gi_type_info_get_param_type (arr_ti, 0);
          if (elem_ti != NULL)
            {
              GITypeTag elem_tag = gi_type_info_get_tag (elem_ti);
              if (elem_tag == GI_TYPE_TAG_FILENAME || elem_tag == GI_TYPE_TAG_UTF8)
                {
                  out->n_args = 1;
                  out->args[0] = PYGI_TY_STRV;
                  out->flags |= PYGI_SIG_ARGV_LEN_PAIR;
                  return 0;
                }
            }
        }
    }

  out->n_args = n_args;
  for (int i = 0; i < n_args; i++)
    {
      g_autoptr (GIArgInfo) ai = gi_callable_info_get_arg (cb, (guint)i);
      if (gi_arg_info_get_direction (ai) != GI_DIRECTION_IN)
        return -1;
      g_autoptr (GITypeInfo) ti = gi_arg_info_get_type_info (ai);
      if (pygi_jit_type_kind_from_gi (ti, &out->args[i]) != 0)
        return -1;
      if (out->args[i] == PYGI_TY_UTF8
          && gi_arg_info_get_ownership_transfer (ai) == GI_TRANSFER_EVERYTHING)
        out->args[i] = PYGI_TY_UTF8_OWNED;
      else if (out->args[i] == PYGI_TY_GOBJECT
               && gi_arg_info_get_ownership_transfer (ai) == GI_TRANSFER_EVERYTHING)
        out->args[i] = PYGI_TY_GOBJECT_OWNED;
    }
  return 0;
}

static void *
resolve_c_symbol (const char *namespace_name, const char *c_symbol)
{
  void *target_fn = dlsym (RTLD_DEFAULT, c_symbol);
  if (target_fn != NULL)
    return target_fn;

  /* Fallback: dlopen the namespace's shared libs and retry. The query
   * uses a fresh GIRepository with only `namespace_name` required -
   * libgirepository 2.88's get_shared_libraries returns the wrong libs
   * on a repo where multiple namespaces have been require()d. The
   * required version comes from pygir's required-version table so we
   * never accidentally pull in a newer parallel-installed typelib (eg
   * libgtk-4 when the process is using Gtk-3.0). */
  const char *version = repository_get_required_version (namespace_name);
  g_autoptr (GIRepository) repo = gi_repository_new ();
  if (repo == NULL)
    return NULL;
  g_autoptr (GError) err = NULL;
  if (gi_repository_require (repo, namespace_name, version, GI_REPOSITORY_LOAD_FLAG_NONE, &err)
      == NULL)
    return NULL;
  size_t n_libs = 0;
  const char *const *libs = gi_repository_get_shared_libraries (repo, namespace_name, &n_libs);
  if (libs != NULL)
    {
      for (size_t i = 0; i < n_libs; i++)
        dlopen (libs[i], RTLD_LAZY | RTLD_GLOBAL);
    }
  return dlsym (RTLD_DEFAULT, c_symbol);
}

/* ------------------------------------------------------------------ */
/* PyGIJitPlan ABI lowering                                          */
/* ------------------------------------------------------------------ */

static void
unsupported (PyGIJitPlan *jp, const char *fmt, ...)
{
  jp->unsupported = true;
  va_list ap;
  va_start (ap, fmt);
  vsnprintf (jp->unsupported_reason, sizeof (jp->unsupported_reason), fmt, ap);
  va_end (ap);
}

/* Map a GI IN-arg type tag to the ABI kind. Returns -1 if the caller
 * should reject the callable. */
static int
abi_kind_for_in_arg (GITypeInfo *ti, PyGIAbiKind *out)
{
  GITypeTag tag = gi_type_info_get_tag (ti);
  if (tag == GI_TYPE_TAG_VOID)
    {
      /* `void *` (gpointer) is GI_TYPE_TAG_VOID with is_pointer() true. */
      if (gi_type_info_is_pointer (ti))
        {
          *out = PYGI_ABI_POINTER;
          return 0;
        }
      return -1;
    }
  return abi_kind_for_return (ti, out);
}

int
pygi_jit_plan_lower (GICallableInfo *cb,
                     const PyGIInvokePlan *invoke,
                     int has_self,
                     PyGIJitPlan *jit_plan)
{
  memset (jit_plan, 0, sizeof (*jit_plan));

  bool can_throw = gi_callable_info_can_throw_gerror (cb);
  jit_plan->can_throw_gerror = can_throw;

  /* Return kind. */
  g_autoptr (GITypeInfo) ret_ti = gi_callable_info_get_return_type (cb);
  if (abi_kind_for_return (ret_ti, &jit_plan->ret_kind) != 0)
    {
      unsupported (jit_plan, "unsupported return type");
      return -1;
    }

  /* Walk: self (if present), every GI arg in declaration order, gerror.
   * For each slot we record:
   *   - the ABI kind (i32, pointer, double, ...)
   *   - where the value lives in the prepared frame:
   *       IN args      -> frame->in_args[ap->in_slot]
   *       OUT/INOUT    -> frame->out_args[ap->out_slot]  (always a pointer)
   *       gerror       -> &frame->gerror
   * The OUT/INOUT case unifies caller-allocates (in_slot=-1) and
   * non-caller-allocates (in_slot>=0): both have out_args[slot].v_pointer
   * holding the right pointer. */
  size_t n_max = (has_self ? 1u : 0u) + invoke->n_gi_args + (can_throw ? 1u : 0u);
  if (n_max > PYGI_JIT_MAX_ABI_ARGS)
    {
      unsupported (jit_plan, "too many ABI args (%zu > %d)", n_max, PYGI_JIT_MAX_ABI_ARGS);
      return -1;
    }

  int n = 0;
  if (has_self)
    {
      jit_plan->abi_args[n++] = (PyGIJitAbiArg){
        .kind = PYGI_ABI_POINTER,
        .source = PYGI_JIT_ARG_FROM_IN_ARG,
        .source_slot = 0,
      };
    }

  for (size_t i = 0; i < invoke->n_gi_args; i++)
    {
      const PyGIArgPlan *ap = &invoke->args[i];
      g_autoptr (GIArgInfo) ai = gi_callable_info_get_arg (cb, ap->gi_index);
      g_autoptr (GITypeInfo) ti = gi_arg_info_get_type_info (ai);

      if (ap->direction == GI_DIRECTION_IN)
        {
          if (ap->in_slot < 0)
            {
              unsupported (jit_plan, "IN arg without in_slot at gi index %u", ap->gi_index);
              return -1;
            }
          PyGIAbiKind kind;
          if (abi_kind_for_in_arg (ti, &kind) != 0)
            {
              unsupported (jit_plan, "unsupported IN arg type at gi index %u", ap->gi_index);
              return -1;
            }
          jit_plan->abi_args[n++] = (PyGIJitAbiArg){
            .kind = kind,
            .source = PYGI_JIT_ARG_FROM_IN_ARG,
            .source_slot = (int)ap->in_slot,
          };
        }
      else /* OUT or INOUT */
        {
          if (ap->out_slot < 0)
            {
              unsupported (jit_plan, "OUT/INOUT arg without out_slot at gi index %u", ap->gi_index);
              return -1;
            }
          jit_plan->abi_args[n++] = (PyGIJitAbiArg){
            .kind = PYGI_ABI_POINTER,
            .source = PYGI_JIT_ARG_FROM_OUT_ARG,
            .source_slot = (int)ap->out_slot,
          };
        }
    }

  if (can_throw)
    {
      jit_plan->abi_args[n++] = (PyGIJitAbiArg){
        .kind = PYGI_ABI_POINTER,
        .source = PYGI_JIT_ARG_FROM_ERROR_PTR,
        .source_slot = -1,
      };
    }

  jit_plan->n_abi_args = n;
  return 0;
}

/* ------------------------------------------------------------------ */
/* PyGICompiledCallable build / destroy                              */
/* ------------------------------------------------------------------ */

static void
invoke_plan_stats_add (const PyGIInvokePlan *plan, long long delta)
{
  if (plan == NULL || plan->args == NULL)
    return;

  pygi_stat_add (PYGI_STAT_INVOKE_PLANS_LIVE, delta);
  for (size_t i = 0; i < plan->n_gi_args; i++)
    {
      const PyGIArgPlan *ap = &plan->args[i];
      if (ap->cached_ai != NULL)
        pygi_stat_add (PYGI_STAT_INVOKE_PLAN_ARG_INFO_REFS_LIVE, delta);
      if (ap->cached_ti != NULL)
        pygi_stat_add (PYGI_STAT_INVOKE_PLAN_TYPE_INFO_REFS_LIVE, delta);
      if (ap->array_elem_ti != NULL)
        pygi_stat_add (PYGI_STAT_INVOKE_PLAN_ARRAY_ELEM_TYPE_INFO_REFS_LIVE, delta);
    }
  if (plan->return_ti != NULL)
    pygi_stat_add (PYGI_STAT_INVOKE_PLAN_RETURN_TYPE_INFO_REFS_LIVE, delta);
}

static int
build_invoke_plan (PyGICompiledCallable *compiled, GICallableInfo *cb, int has_self)
{
  size_t n = gi_callable_info_get_n_args (cb);
  /* pygi_invoke_plan asserts plan->args/out_slots != NULL even for n==0,
   * so always allocate at least one slot. */
  size_t n_alloc = n > 0 ? n : 1u;

  PyGIArgPlan *args = calloc (n_alloc, sizeof (*args));
  PyGIOutSlotPlan *outs = calloc (n_alloc, sizeof (*outs));
  if (args == NULL || outs == NULL)
    {
      free (args);
      free (outs);
      return -1;
    }
  for (size_t k = 0; k < n; k++)
    {
      args[k].py_arg_index = -1;
      args[k].in_slot = -1;
      args[k].out_slot = -1;
      args[k].length_arg = -1;
      args[k].owner_array_arg = -1;
      outs[k].paired_length_out_slot = -1;
      outs[k].paired_length_in_slot = -1;
      outs[k].paired_in_length_gi_arg = -1;
    }

  compiled->invoke_plan_args = args;
  compiled->invoke_plan_outs = outs;
  compiled->invoke_plan.args = args;
  compiled->invoke_plan.out_slots = outs;

  /* SIZE_MAX = "skip closure-arity validation, trust GI metadata".
   * At call time, if the actual nargs doesn't match the post-skip
   * count, the binder reverts the closure roles for that one call. */
  pygi_invoke_plan (cb, has_self, SIZE_MAX, &compiled->invoke_plan);
  pygi_stat_inc (PYGI_STAT_INVOKE_PLANS_TOTAL);
  invoke_plan_stats_add (&compiled->invoke_plan, 1);

  /* Tag callables that have closure-companion args so the bind/prepare
   * fast path knows it may need to reinterpret roles per call. */
  for (size_t i = 0; i < compiled->invoke_plan.n_gi_args; i++)
    if (compiled->invoke_plan.args[i].role == PYGI_ARG_ROLE_CLOSURE_DESTROY)
      {
        compiled->has_closure_companions = true;
        break;
      }
  return 0;
}

PyGICompiledCallable *
pygi_jit_compile_callable (GIFunctionInfo *info, int has_self, const char *qualified_name)
{
  /* Resolve the symbol first - if we can't find it, no JIT path can run. */
  const char *c_symbol = gi_function_info_get_symbol (info);
  const char *namespace_name = gi_base_info_get_namespace ((GIBaseInfo *)info);
  void *target_fn = c_symbol != NULL ? resolve_c_symbol (namespace_name, c_symbol) : NULL;
  if (target_fn == NULL)
    return NULL;

  PyGICompiledCallable *compiled = calloc (1, sizeof (*compiled));
  if (compiled == NULL)
    return NULL;
  pygi_stat_inc (PYGI_STAT_COMPILED_CALLABLES_LIVE);
  pygi_stat_inc (PYGI_STAT_COMPILED_CALLABLES_TOTAL);
  compiled->info = (GICallableInfo *)gi_base_info_ref ((GIBaseInfo *)info);
  pygi_stat_inc (PYGI_STAT_COMPILED_CALLABLE_INFO_REFS_LIVE);
  compiled->qualified_name = qualified_name != NULL ? strdup (qualified_name) : NULL;
  compiled->target_fn = target_fn;
  compiled->has_self = has_self;

  if (build_invoke_plan (compiled, (GICallableInfo *)info, has_self) != 0)
    {
      pygi_jit_compiled_callable_destroy (compiled);
      return NULL;
    }

  /* Pre-compute the per-call arena size - the trampoline reserves this
   * many bytes on its own stack and passes a pointer to prepare. */
  {
    size_t n = compiled->invoke_plan.n_gi_args;
    size_t mi = compiled->invoke_plan.n_in_args;
    size_t mo = compiled->invoke_plan.n_out_args > 0 ? compiled->invoke_plan.n_out_args : n;
    compiled->arena_size = pygi_jit_arena_size_for (n, mi, mo);
  }

  /* Precompute the FFI cif + atypes table once. The slow-FFI fallback
   * was burning a measurable chunk per call walking the GIR signature
   * to (re)compute these. The plan already cached cached_ai/cached_ti
   * so we just read off them. */
  {
    GICallableInfo *cb = (GICallableInfo *)info;
    PyGIInvokePlan *plan = &compiled->invoke_plan;
    bool throws = gi_callable_info_can_throw_gerror (cb);
    unsigned int n_args = (unsigned int)plan->n_gi_args;
    unsigned int n_invoke_args = n_args + (has_self ? 1u : 0u) + (throws ? 1u : 0u);
    compiled->ffi_rinfo = gi_callable_info_get_return_type (cb);
    if (compiled->ffi_rinfo != NULL)
      pygi_stat_inc (PYGI_STAT_FFI_RETURN_TYPE_INFO_REFS_LIVE);
    compiled->ffi_rtag = gi_type_info_get_tag (compiled->ffi_rinfo);
    /* Same LLP64 fix as the GTYPE in-args: girepository maps GI_TYPE_TAG_GTYPE
       to the 32-bit ffi_type_ulong on Windows, truncating a returned 64-bit
       GType (registered types are pointer-width). Use a pointer-width ffi
       return type so g_type_from_name() & friends survive. */
    compiled->ffi_rtype = (compiled->ffi_rtag == GI_TYPE_TAG_GTYPE)
                              ? &ffi_type_pointer
                              : gi_type_info_get_ffi_type (compiled->ffi_rinfo);
    compiled->ffi_return_is_pointer = gi_type_info_is_pointer (compiled->ffi_rinfo);
    compiled->ffi_throws = throws;
    compiled->ffi_n_invoke_args = n_invoke_args;
    compiled->ffi_atypes
        = (ffi_type **)calloc (n_invoke_args ? n_invoke_args : 1u, sizeof (ffi_type *));
    if (compiled->ffi_atypes == NULL)
      {
        pygi_jit_compiled_callable_destroy (compiled);
        return NULL;
      }
    unsigned int slot = 0;
    if (has_self)
      compiled->ffi_atypes[slot++] = &ffi_type_pointer;
    for (unsigned int i = 0; i < n_args; i++)
      {
        const PyGIArgPlan *ap = &plan->args[i];
        if (ap->direction == GI_DIRECTION_IN)
          {
            /* girepository maps GI_TYPE_TAG_GTYPE to ffi_type_ulong, which is
               only 32-bit on LLP64 (Windows) and truncates the 64-bit GType
               (GType is gsize, i.e. pointer-width). Pass it as a pointer-width
               integer so the full value survives the ffi call. */
            if (ap->tag == GI_TYPE_TAG_GTYPE)
              compiled->ffi_atypes[slot++] = &ffi_type_pointer;
            else
              compiled->ffi_atypes[slot++] = gi_type_info_get_ffi_type (ap->cached_ti);
          }
        else
          compiled->ffi_atypes[slot++] = &ffi_type_pointer; /* OUT/INOUT */
      }
    if (throws)
      compiled->ffi_atypes[slot++] = &ffi_type_pointer;
    if (ffi_prep_cif (&compiled->ffi_cif,
                      FFI_DEFAULT_ABI,
                      n_invoke_args,
                      compiled->ffi_rtype,
                      compiled->ffi_atypes)
        == FFI_OK)
      compiled->ffi_setup_ready = true;
  }

  /* Try ABI lowering for the full JIT path. */
  if (pygi_jit_plan_lower ((GICallableInfo *)info,
                           &compiled->invoke_plan,
                           has_self,
                           &compiled->jit_plan)
      == 0)
    {
      PyGIJittedTrampoline tramp = pygi_jit_emit_full_x86_64 (compiled, qualified_name);
      if (tramp != NULL)
        {
          compiled->trampoline = tramp;
          compiled->trampoline_is_full = true;
          return compiled;
        }
    }

  /* Fall back to the legacy narrow PyGISignature emitter. */
  if (narrow_signature_from_callable ((GICallableInfo *)info, has_self, &compiled->signature) == 0)
    {
      PyGIJittedTrampoline tramp
          = pygi_jit_emit_with_name (target_fn, &compiled->signature, qualified_name);
      if (tramp != NULL)
        {
          compiled->trampoline = tramp;
          compiled->has_narrow_signature = true;
          return compiled;
        }
    }

  pygi_jit_compiled_callable_destroy (compiled);
  return NULL;
}

void
pygi_jit_compiled_callable_destroy (PyGICompiledCallable *compiled)
{
  if (compiled == NULL)
    return;
  pygi_stat_dec (PYGI_STAT_COMPILED_CALLABLES_LIVE);
  /* Release plan-owned cached_ai/cached_ti before freeing args storage. */
  invoke_plan_stats_add (&compiled->invoke_plan, -1);
  pygi_invoke_plan_clear (&compiled->invoke_plan);
  if (compiled->ffi_rinfo != NULL)
    {
      pygi_stat_dec (PYGI_STAT_FFI_RETURN_TYPE_INFO_REFS_LIVE);
      gi_base_info_unref ((GIBaseInfo *)compiled->ffi_rinfo);
    }
  free (compiled->ffi_atypes);
  if (compiled->info != NULL)
    {
      pygi_stat_dec (PYGI_STAT_COMPILED_CALLABLE_INFO_REFS_LIVE);
      gi_base_info_unref ((GIBaseInfo *)compiled->info);
    }
  free (compiled->qualified_name);
  free (compiled->invoke_plan_args);
  free (compiled->invoke_plan_outs);
  /* Trampoline lifetime is process-wide for now. */
  free (compiled);
}
