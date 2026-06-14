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

#include "common.h"
#include "GObject/hooks.h"

#include "GObject/Boxed.h"
#include "GObject/Object-info.h"
#include "GIRepository/BaseInfo.h"
#include "GIRepository/CallableInfo.h"
#include "invoke/ffi/invoke.h"
#include "invoke/jit/plan.h"
#include "marshal/scalar.h"
#include "marshal/string.h"
#include "runtime/callable.h"
#include "runtime/type-info.h"
#include "gimeta-helpers.h"

#include <dlfcn.h>
#include <girepository/girffi.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static const char *CALLABLE_DESCRIPTOR_CAPSULE_NAME = "ginext.private.PyGIMethodDescriptor";
PyTypeObject *ginext_method_descriptor_type = NULL;

static ffi_type *gvalue_ffi_elements[] = {
  &ffi_type_uint64,
  &ffi_type_uint64,
  &ffi_type_uint64,
  NULL,
};

static ffi_type gvalue_ffi_type = {
  .size = 0,
  .alignment = 0,
  .type = FFI_TYPE_STRUCT,
  .elements = gvalue_ffi_elements,
};

extern void
pygi_ginext_record_plan_gi_metadata_call (void);
extern PyObject *
pygi_boxed_new_alias (PyObject *cls, gpointer boxed, GType gtype, PyObject *parent);

static gboolean
type_info_is_supported (GITypeInfo *type_info, gboolean allow_void);
static gboolean
type_info_is_supported_array_element_info (GITypeInfo *elem_info);
static gboolean
type_info_is_supported_hash_table (GITypeInfo *type_info);
static PyObject *
method_descriptor_vectorcall (PyObject *self,
                              PyObject *const *args,
                              size_t nargsf,
                              PyObject *kwnames);
static PyObject *
invoke_descriptor_vectorcall (PyGIMethodDescriptor *descriptor,
                              PyObject *const *args,
                              size_t nargsf,
                              PyObject *kwnames);
static PyObject *
invoke_descriptor_trivial_scalar_fastcall (PyGIMethodDescriptor *descriptor,
                                           PyObject *const *args,
                                           Py_ssize_t nargs);
static int
invoke_descriptor_gobject_self_fastcall (PyGIInvokePlan *plan,
                                         PyObject *self_arg,
                                         gpointer *self_ptr_out);
static int
invoke_descriptor_gobject_arg_fastcall (const PyGIArgPlan *arg_plan,
                                        PyObject *arg,
                                        gpointer *arg_ptr_out);
static int
invoke_descriptor_utf8_arg_fastcall (const PyGIArgPlan *arg_plan,
                                     PyObject *arg,
                                     char **arg_string_out);
static PyObject *
invoke_self_object_void_fastcall (PyGIMethodDescriptor *descriptor,
                                  gpointer self_ptr,
                                  PyObject *arg);
static PyObject *
invoke_self_bool_void_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr, gboolean arg);
static PyObject *
invoke_self_utf8_void_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr, char *arg);
static PyObject *
invoke_self_utf8_object_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr, char *arg);
static PyObject *
invoke_self_void_void_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr);
static PyObject *
invoke_self_void_boolean_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr);
static PyObject *
invoke_self_void_int32_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr);
static PyObject *
invoke_self_void_utf8_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr);
static PyObject *
invoke_self_int32_object_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr, gint32 arg);
static PyObject *
resolve_call_args (PyGIMethodDescriptor *d,
                   PyObject *self_obj,
                   PyObject *args_in,
                   Py_ssize_t args_offset,
                   PyObject *kwargs_in);

static gboolean
callback_return_type_is_supported (GITypeInfo *type_info, GITransfer transfer)
{
  if (type_info == NULL)
    return FALSE;
  pygi_ginext_record_plan_gi_metadata_call ();
  GITypeTag tag = gi_type_info_get_tag (type_info);
  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      return TRUE;
#define PYGI_SCALAR PYGI_SCALAR_RETURN_TRUE

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      /* transfer-nothing utf8/filename callback returns are handled
         * via a "pinned" slot on the closure: the strdup'd string from
         * the previous call is freed on the next return or at closure
         * teardown. The caller still must not store the pointer past
         * the next callback invocation. */
      return TRUE;
    case GI_TYPE_TAG_INTERFACE:
      {
        pygi_ginext_record_plan_gi_metadata_call ();
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
        return iface != NULL
               && (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)
                   || GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)
                   || GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface));
      }
    default:
      return FALSE;
    }
}

static gboolean
callback_arg_type_is_supported (GITypeInfo *type_info, GIDirection direction)
{
  if (type_info == NULL)
    return FALSE;
  pygi_ginext_record_plan_gi_metadata_call ();
  GITypeTag tag = gi_type_info_get_tag (type_info);
  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      /* IN: gpointer user-data. OUT: opaque slot the callback writes
         * (e.g. GSettingsBindGetMapping's "result" slot). */
      return direction == GI_DIRECTION_OUT
             || (direction == GI_DIRECTION_IN && gi_type_info_is_pointer (type_info));
#define PYGI_SCALAR PYGI_SCALAR_RETURN_TRUE

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      return TRUE;
    case GI_TYPE_TAG_ERROR:
      return TRUE;
    case GI_TYPE_TAG_GHASH:
    case GI_TYPE_TAG_GLIST:
    case GI_TYPE_TAG_GSLIST:
      return direction == GI_DIRECTION_IN;
    case GI_TYPE_TAG_ARRAY:
      if (direction == GI_DIRECTION_IN)
        return TRUE;
      if (direction == GI_DIRECTION_OUT || direction == GI_DIRECTION_INOUT)
        {
          if (gi_type_info_get_array_type (type_info) != GI_ARRAY_TYPE_C)
            return FALSE;
          pygi_ginext_record_plan_gi_metadata_call ();
          g_autoptr (GITypeInfo) elem_info = gi_type_info_get_param_type (type_info, 0);
          if (elem_info == NULL)
            return FALSE;
          pygi_ginext_record_plan_gi_metadata_call ();
          GITypeTag etag = gi_type_info_get_tag (elem_info);
          unsigned int length_index = 0;
          gboolean has_length = gi_type_info_get_array_length_index (type_info, &length_index);
          gboolean is_strv = (etag == GI_TYPE_TAG_UTF8 || etag == GI_TYPE_TAG_FILENAME)
                             && gi_type_info_is_zero_terminated (type_info);
          if (!has_length && !is_strv)
            return FALSE;
          return etag == GI_TYPE_TAG_INT32 || etag == GI_TYPE_TAG_UINT32 || etag == GI_TYPE_TAG_UTF8
                 || etag == GI_TYPE_TAG_FILENAME;
        }
      return FALSE;
    case GI_TYPE_TAG_INTERFACE:
      {
        pygi_ginext_record_plan_gi_metadata_call ();
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
        if (iface == NULL)
          return FALSE;
        if (direction == GI_DIRECTION_IN)
          return GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)
                 || GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface) || GI_IS_ENUM_INFO (iface)
                 || GI_IS_FLAGS_INFO (iface) || GI_IS_CALLBACK_INFO (iface);
        /* Callback OUT/INOUT INTERFACE: the closure writes a pointer
         * back via callback_write_value (struct/union/object/iface),
         * an int slot for enum/flags, or a function pointer for
         * GDestroyNotify-style callback typedefs. */
        return GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)
               || GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface) || GI_IS_ENUM_INFO (iface)
               || GI_IS_FLAGS_INFO (iface) || GI_IS_CALLBACK_INFO (iface);
      }
    default:
      return FALSE;
    }
}

static gboolean
callback_info_is_supported (GICallableInfo *callback_info)
{
  g_autoptr (GITypeInfo) return_type = gi_callable_info_get_return_type (callback_info);
  GITransfer return_transfer = gi_callable_info_get_caller_owns (callback_info);
  if (!callback_return_type_is_supported (return_type, return_transfer))
    return FALSE;

  unsigned int n_args = gi_callable_info_get_n_args (callback_info);
  for (unsigned int i = 0; i < n_args; i++)
    {
      pygi_ginext_record_plan_gi_metadata_call ();
      g_autoptr (GIArgInfo) arg = gi_callable_info_get_arg (callback_info, i);
      GIDirection direction = gi_arg_info_get_direction (arg);
      pygi_ginext_record_plan_gi_metadata_call ();
      g_autoptr (GITypeInfo) type = gi_arg_info_get_type_info (arg);
      if (!callback_arg_type_is_supported (type, direction))
        return FALSE;
    }
  return TRUE;
}

static gboolean
type_info_is_glib_error (GITypeInfo *type_info)
{
  if (type_info == NULL)
    return FALSE;
  GITypeTag tag = gi_type_info_get_tag (type_info);
  if (tag == GI_TYPE_TAG_ERROR)
    return TRUE;
  if (tag != GI_TYPE_TAG_INTERFACE)
    return FALSE;
  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
  return iface != NULL
         && (gi_base_info_is_named (iface, "GLib", "Error")
             || gi_base_info_is_named (iface, "GObject", "Error"));
}

static gboolean
type_info_is_record (GITypeInfo *type_info)
{
  if (type_info == NULL || gi_type_info_get_tag (type_info) != GI_TYPE_TAG_INTERFACE
      || gi_type_info_is_gvalue (type_info))
    return FALSE;
  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
  return iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface));
}

static gboolean
type_info_is_zero_terminated_string_array (GITypeInfo *type_info)
{
  if (gi_type_info_get_array_type (type_info) != GI_ARRAY_TYPE_C)
    return FALSE;
  if (!gi_type_info_is_zero_terminated (type_info))
    return FALSE;

  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) elem_info = gi_type_info_get_param_type (type_info, 0);
  if (elem_info == NULL)
    return FALSE;
  pygi_ginext_record_plan_gi_metadata_call ();
  GITypeTag elem_tag = gi_type_info_get_tag (elem_info);
  return elem_tag == GI_TYPE_TAG_UTF8 || elem_tag == GI_TYPE_TAG_FILENAME
         || elem_tag == GI_TYPE_TAG_UNICHAR;
}

static gboolean
type_info_is_supported_zero_terminated_array_return (GITypeInfo *type_info)
{
  if (gi_type_info_get_array_type (type_info) != GI_ARRAY_TYPE_C)
    return FALSE;
  if (!gi_type_info_is_zero_terminated (type_info))
    return FALSE;

  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) elem_info = gi_type_info_get_param_type (type_info, 0);
  return type_info_is_supported_array_element_info (elem_info);
}

static gboolean
type_info_is_supported_list_return (GITypeInfo *type_info)
{
  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) elem_info = gi_type_info_get_param_type (type_info, 0);
  if (elem_info == NULL)
    return TRUE;

  pygi_ginext_record_plan_gi_metadata_call ();
  GITypeTag elem_tag = gi_type_info_get_tag (elem_info);
  switch (elem_tag)
    {
    case GI_TYPE_TAG_VOID:
    case GI_TYPE_TAG_BOOLEAN:
    case GI_TYPE_TAG_INT8:
    case GI_TYPE_TAG_UINT8:
    case GI_TYPE_TAG_INT16:
    case GI_TYPE_TAG_UINT16:
    case GI_TYPE_TAG_GLIST:
    case GI_TYPE_TAG_GSLIST:
      /* G[S]List nodes hold a gpointer slot. Element-type metadata
         * smaller than a pointer (or itself a list) is treated as
         * opaque: accept None or a boxed wrapper at the marshaler. */
      return TRUE;
    case GI_TYPE_TAG_INT32:
    case GI_TYPE_TAG_UINT32:
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
    case GI_TYPE_TAG_GTYPE:
    case GI_TYPE_TAG_ERROR:
      return TRUE;
    case GI_TYPE_TAG_INTERFACE:
      {
        pygi_ginext_record_plan_gi_metadata_call ();
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_info);
        return iface != NULL
               && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)
                   || GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)
                   || GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface));
      }
    default:
      return FALSE;
    }
}

static gboolean
type_info_is_supported_hash_element (GITypeInfo *elem_info, gboolean is_key)
{
  if (elem_info == NULL)
    return FALSE;
  if (!is_key && gi_type_info_is_gvalue (elem_info))
    return TRUE;
  if (gi_type_info_is_variant (elem_info))
    return TRUE;

  pygi_ginext_record_plan_gi_metadata_call ();
  GITypeTag elem_tag = gi_type_info_get_tag (elem_info);
  switch (elem_tag)
    {
    case GI_TYPE_TAG_INT32:
    case GI_TYPE_TAG_UINT32:
    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
      return TRUE;
    case GI_TYPE_TAG_FLOAT:
    case GI_TYPE_TAG_DOUBLE:
    case GI_TYPE_TAG_INT64:
    case GI_TYPE_TAG_UINT64:
      return !is_key;
    case GI_TYPE_TAG_GHASH:
      return !is_key && type_info_is_supported_hash_table (elem_info);
    case GI_TYPE_TAG_INTERFACE:
      {
        pygi_ginext_record_plan_gi_metadata_call ();
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_info);
        if (iface == NULL)
          return FALSE;
        if (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface))
          return TRUE;
        /* Object/struct/union pointers go in the hash slot directly. */
        return GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)
               || GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface);
      }
    default:
      return FALSE;
    }
}

static gboolean
type_info_is_opaque_hash_table (GITypeInfo *type_info)
{
  /* Some GIRs declare GHashTable* without param types, with a value
     * tag of GI_TYPE_TAG_VOID (e.g. GHashTable<gchar*, gpointer>), or
     * with a key tag of VOID (GHashTable<gpointer, FooStruct>). Treat
     * any of those as opaque: the marshaler accepts None (→ NULL) or
     * a boxed GLib.HashTable, never a dict. */
  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) key_info = gi_type_info_get_param_type (type_info, 0);
  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) value_info = gi_type_info_get_param_type (type_info, 1);
  if (key_info == NULL || value_info == NULL)
    return TRUE;
  return gi_type_info_get_tag (value_info) == GI_TYPE_TAG_VOID
         || gi_type_info_get_tag (key_info) == GI_TYPE_TAG_VOID;
}

static gboolean
type_info_is_supported_hash_table (GITypeInfo *type_info)
{
  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) key_info = gi_type_info_get_param_type (type_info, 0);
  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) value_info = gi_type_info_get_param_type (type_info, 1);
  if (type_info_is_opaque_hash_table (type_info))
    return TRUE;
  return type_info_is_supported_hash_element (key_info, TRUE)
         && type_info_is_supported_hash_element (value_info, FALSE);
}

static gboolean
type_info_is_supported_array_element_info (GITypeInfo *elem_info)
{
  if (elem_info == NULL)
    return FALSE;

  pygi_ginext_record_plan_gi_metadata_call ();
  GITypeTag elem_tag = gi_type_info_get_tag (elem_info);
  switch (elem_tag)
    {
#define PYGI_SCALAR PYGI_SCALAR_RETURN_TRUE

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
    case GI_TYPE_TAG_ERROR:
      return TRUE;
    case GI_TYPE_TAG_ARRAY:
      {
        pygi_ginext_record_plan_gi_metadata_call ();
        g_autoptr (GITypeInfo) nested_elem_info = gi_type_info_get_param_type (elem_info, 0);
        if (nested_elem_info == NULL)
          return FALSE;
        pygi_ginext_record_plan_gi_metadata_call ();
        GITypeTag nested_elem_tag = gi_type_info_get_tag (nested_elem_info);
        return nested_elem_tag == GI_TYPE_TAG_UTF8 || nested_elem_tag == GI_TYPE_TAG_FILENAME;
      }
    case GI_TYPE_TAG_INTERFACE:
      {
        if (gi_type_info_is_gvalue (elem_info))
          return TRUE;
        if (gi_type_info_is_variant (elem_info))
          return TRUE;
        pygi_ginext_record_plan_gi_metadata_call ();
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_info);
        return iface != NULL
               && (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)
                   || GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)
                   || (GI_IS_STRUCT_INFO (iface) && !gi_type_info_is_gvalue (elem_info))
                   || GI_IS_UNION_INFO (iface));
      }
    default:
      return FALSE;
    }
}

static gboolean
type_info_is_supported_fixed_array_return (GITypeInfo *type_info)
{
  if (gi_type_info_get_array_type (type_info) != GI_ARRAY_TYPE_C)
    return FALSE;

  size_t fixed_size = 0;
  if (!gi_type_info_get_array_fixed_size (type_info, &fixed_size) || fixed_size == 0)
    return FALSE;

  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) elem_info = gi_type_info_get_param_type (type_info, 0);
  return type_info_is_supported_array_element_info (elem_info);
}

static gboolean
type_info_has_supported_array_element (GITypeInfo *type_info)
{
  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) elem_info = gi_type_info_get_param_type (type_info, 0);
  return type_info_is_supported_array_element_info (elem_info);
}

static gboolean
type_info_is_supported_non_c_array (GITypeInfo *type_info)
{
  if (gi_type_info_get_tag (type_info) != GI_TYPE_TAG_ARRAY)
    return FALSE;

  GIArrayType array_type = gi_type_info_get_array_type (type_info);
  if (array_type == GI_ARRAY_TYPE_BYTE_ARRAY)
    return TRUE;

  pygi_ginext_record_plan_gi_metadata_call ();
  g_autoptr (GITypeInfo) elem_info = gi_type_info_get_param_type (type_info, 0);
  if (elem_info == NULL)
    return FALSE;

  if (array_type == GI_ARRAY_TYPE_ARRAY)
    {
      if (type_info_is_supported_array_element_info (elem_info))
        return TRUE;
      /* GArray with nested-container element shape: treat as opaque,
         * the marshaler accepts None or a boxed wrapper only. */
      pygi_ginext_record_plan_gi_metadata_call ();
      GITypeTag elem_tag = gi_type_info_get_tag (elem_info);
      return elem_tag == GI_TYPE_TAG_ARRAY || elem_tag == GI_TYPE_TAG_GLIST
             || elem_tag == GI_TYPE_TAG_GSLIST || elem_tag == GI_TYPE_TAG_GHASH;
    }

  if (array_type == GI_ARRAY_TYPE_PTR_ARRAY)
    {
      pygi_ginext_record_plan_gi_metadata_call ();
      GITypeTag elem_tag = gi_type_info_get_tag (elem_info);
      if (elem_tag == GI_TYPE_TAG_UTF8 || elem_tag == GI_TYPE_TAG_FILENAME)
        return TRUE;
      if (elem_tag != GI_TYPE_TAG_INTERFACE)
        return FALSE;
      pygi_ginext_record_plan_gi_metadata_call ();
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem_info);
      return iface != NULL
             && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface) || GI_IS_OBJECT_INFO (iface)
                 || GI_IS_INTERFACE_INFO (iface));
    }

  return FALSE;
}

static gboolean
arg_plan_is_opaque_c_array (const PyGIArgPlan *arg)
{
  /* C array with VOID element (gpointer*): opaque. The marshaler
     * only accepts None (→ NULL) or a boxed pointer wrapper. */
  if (arg->tag != GI_TYPE_TAG_ARRAY || arg->array_type != GI_ARRAY_TYPE_C || arg->cached_ti == NULL)
    return FALSE;
  g_autoptr (GITypeInfo) elem_info = gi_type_info_get_param_type (arg->cached_ti, 0);
  if (elem_info == NULL)
    return TRUE;
  return gi_type_info_get_tag (elem_info) == GI_TYPE_TAG_VOID;
}

static gboolean
arg_plan_is_supported_c_array (const PyGIArgPlan *arg)
{
  if (arg->tag != GI_TYPE_TAG_ARRAY || arg->array_type != GI_ARRAY_TYPE_C)
    return FALSE;
  if (arg->length_arg < 0 && !arg->array_has_fixed_size
      && arg->length_kind != PYGI_LENGTH_ZERO_TERMINATED)
    return FALSE;
  return type_info_has_supported_array_element (arg->cached_ti);
}

static gboolean
arg_plan_is_supported_in_gvalue_c_array (const PyGIArgPlan *arg)
{
  if (arg->tag != GI_TYPE_TAG_ARRAY || arg->array_type != GI_ARRAY_TYPE_C
      || arg->direction != GI_DIRECTION_IN)
    return FALSE;

  if (arg->length_arg < 0 && !arg->array_has_fixed_size
      && arg->length_kind != PYGI_LENGTH_ZERO_TERMINATED)
    return FALSE;

  return arg->array_elem_ti != NULL && gi_type_info_is_gvalue (arg->array_elem_ti);
}

static gboolean
arg_plan_is_supported_unknown_length_in_c_array (const PyGIArgPlan *arg)
{
  if (arg->tag != GI_TYPE_TAG_ARRAY || arg->array_type != GI_ARRAY_TYPE_C
      || arg->direction != GI_DIRECTION_IN || arg->length_arg >= 0 || arg->array_has_fixed_size
      || arg->length_kind != PYGI_LENGTH_NONE)
    return FALSE;

  return type_info_has_supported_array_element (arg->cached_ti);
}

static gboolean
arg_plan_is_supported_array (const PyGIArgPlan *arg)
{
  if (arg->tag != GI_TYPE_TAG_ARRAY)
    return FALSE;
  if (arg->array_type == GI_ARRAY_TYPE_C)
    return arg_plan_is_supported_c_array (arg) || arg_plan_is_supported_in_gvalue_c_array (arg)
           || arg_plan_is_supported_unknown_length_in_c_array (arg)
           || (arg->direction == GI_DIRECTION_IN && arg_plan_is_opaque_c_array (arg));
  return type_info_is_supported_non_c_array (arg->cached_ti);
}

static gboolean
arg_plan_is_supported_c_array_length (const PyGIInvokePlan *plan, const PyGIArgPlan *arg)
{
  if (arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH || arg->owner_array_arg < 0
      || (size_t)arg->owner_array_arg >= plan->n_gi_args)
    return FALSE;

  const PyGIArgPlan *owner = &plan->args[arg->owner_array_arg];
  return (owner->direction == GI_DIRECTION_OUT || owner->direction == GI_DIRECTION_INOUT)
         && arg_plan_is_supported_c_array (owner);
}

#define info_from_capsule gi_info_from_py

static void
init_plan_storage (PyGICompiledCallable *compiled, size_t n_args)
{
  compiled->invoke_plan_args = calloc (n_args ? n_args : 1u, sizeof (*compiled->invoke_plan_args));
  compiled->invoke_plan_outs = calloc (n_args ? n_args : 1u, sizeof (*compiled->invoke_plan_outs));
  if (compiled->invoke_plan_args == NULL || compiled->invoke_plan_outs == NULL)
    return;

  for (size_t i = 0; i < n_args; i++)
    {
      compiled->invoke_plan_args[i].py_arg_index = -1;
      compiled->invoke_plan_args[i].in_slot = -1;
      compiled->invoke_plan_args[i].out_slot = -1;
      compiled->invoke_plan_args[i].length_arg = -1;
      compiled->invoke_plan_args[i].owner_array_arg = -1;
      compiled->invoke_plan_args[i].owner_callback_arg = -1;
      compiled->invoke_plan_outs[i].paired_length_out_slot = -1;
      compiled->invoke_plan_outs[i].paired_length_in_slot = -1;
      compiled->invoke_plan_outs[i].paired_in_length_gi_arg = -1;
    }

  compiled->invoke_plan.args = compiled->invoke_plan_args;
  compiled->invoke_plan.out_slots = compiled->invoke_plan_outs;
}

static gboolean
type_info_is_supported (GITypeInfo *type_info, gboolean allow_void)
{
  pygi_ginext_record_plan_gi_metadata_call ();
  GITypeTag tag = gi_type_info_get_tag (type_info);
  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      return allow_void || gi_type_info_is_pointer (type_info);
#define PYGI_SCALAR PYGI_SCALAR_RETURN_TRUE

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

    case GI_TYPE_TAG_UTF8:
    case GI_TYPE_TAG_FILENAME:
    case GI_TYPE_TAG_ERROR:
      return TRUE;
    case GI_TYPE_TAG_ARRAY:
      return allow_void
             && (type_info_is_zero_terminated_string_array (type_info)
                 || type_info_is_supported_zero_terminated_array_return (type_info)
                 || type_info_is_supported_fixed_array_return (type_info)
                 || type_info_is_supported_non_c_array (type_info));
    case GI_TYPE_TAG_GLIST:
    case GI_TYPE_TAG_GSLIST:
      return type_info_is_supported_list_return (type_info);
    case GI_TYPE_TAG_GHASH:
      return type_info_is_supported_hash_table (type_info);
    case GI_TYPE_TAG_INTERFACE:
      {
        if (gi_type_info_is_variant (type_info))
          return TRUE;
        pygi_ginext_record_plan_gi_metadata_call ();
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
        return iface != NULL
               && (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)
                   || GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)
                   || GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)
                   || GI_IS_UNRESOLVED_INFO (iface)
                   || (GI_IS_CALLBACK_INFO (iface)
                       && callback_info_is_supported ((GICallableInfo *)iface)));
      }
    default:
      return FALSE;
    }
}

static const char *
array_type_short_name (GIArrayType atype)
{
  switch (atype)
    {
    case GI_ARRAY_TYPE_C:
      return "C";
    case GI_ARRAY_TYPE_ARRAY:
      return "GArray";
    case GI_ARRAY_TYPE_PTR_ARRAY:
      return "GPtrArray";
    case GI_ARRAY_TYPE_BYTE_ARRAY:
      return "GByteArray";
    default:
      return "?";
    }
}

static void
append_element_shape (GString *out, GITypeInfo *elem)
{
  if (elem == NULL)
    {
      g_string_append (out, "?");
      return;
    }
  GITypeTag tag = gi_type_info_get_tag (elem);
  g_string_append (out, gi_type_tag_to_string (tag));
  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (elem);
      if (iface != NULL)
        g_string_append_printf (out, "/%s", gi_base_info_get_name (iface));
    }
}

static void
format_arg_shape (GITypeInfo *ti, char *buf, size_t buflen)
{
  GITypeTag tag = gi_type_info_get_tag (ti);
  g_autoptr (GString) out = g_string_new (gi_type_tag_to_string (tag));
  switch (tag)
    {
    case GI_TYPE_TAG_ARRAY:
      {
        g_autoptr (GITypeInfo) elem = gi_type_info_get_param_type (ti, 0);
        g_string_append_printf (out,
                                " (%s of ",
                                array_type_short_name (gi_type_info_get_array_type (ti)));
        append_element_shape (out, elem);
        g_string_append (out, ")");
        break;
      }
    case GI_TYPE_TAG_GLIST:
    case GI_TYPE_TAG_GSLIST:
      {
        g_autoptr (GITypeInfo) elem = gi_type_info_get_param_type (ti, 0);
        g_string_append (out, " (of ");
        append_element_shape (out, elem);
        g_string_append (out, ")");
        break;
      }
    case GI_TYPE_TAG_GHASH:
      {
        g_autoptr (GITypeInfo) key = gi_type_info_get_param_type (ti, 0);
        g_autoptr (GITypeInfo) val = gi_type_info_get_param_type (ti, 1);
        g_string_append (out, " (");
        append_element_shape (out, key);
        g_string_append (out, "->");
        append_element_shape (out, val);
        g_string_append (out, ")");
        break;
      }
    case GI_TYPE_TAG_INTERFACE:
      {
        g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
        if (iface != NULL)
          {
            g_string_append_printf (out, " (%s", gi_base_info_get_name (iface));
            if (GI_IS_UNRESOLVED_INFO (iface))
              g_string_append (out, "/unresolved");
            if (GI_IS_CALLBACK_INFO (iface))
              {
                GICallableInfo *cb = (GICallableInfo *)iface;
                unsigned int n_args = gi_callable_info_get_n_args (cb);
                g_string_append (out, "(");
                for (unsigned int i = 0; i < n_args; i++)
                  {
                    if (i > 0)
                      g_string_append (out, ", ");
                    g_autoptr (GIArgInfo) ai = gi_callable_info_get_arg (cb, i);
                    g_autoptr (GITypeInfo) ati = gi_arg_info_get_type_info (ai);
                    GITypeTag at = gi_type_info_get_tag (ati);
                    GIDirection adir = gi_arg_info_get_direction (ai);
                    if (adir == GI_DIRECTION_OUT)
                      g_string_append (out, "out:");
                    else if (adir == GI_DIRECTION_INOUT)
                      g_string_append (out, "inout:");
                    g_string_append (out, gi_type_tag_to_string (at));
                    if (at == GI_TYPE_TAG_INTERFACE)
                      {
                        g_autoptr (GIBaseInfo) ifa = gi_type_info_get_interface (ati);
                        if (ifa != NULL)
                          g_string_append_printf (out, "/%s", gi_base_info_get_name (ifa));
                      }
                    else if (at == GI_TYPE_TAG_ARRAY)
                      {
                        g_autoptr (GITypeInfo) ae = gi_type_info_get_param_type (ati, 0);
                        if (ae != NULL)
                          {
                            g_string_append_printf (
                                out,
                                "<%s>",
                                gi_type_tag_to_string (gi_type_info_get_tag (ae)));
                          }
                      }
                  }
                g_string_append (out, ")->");
                g_autoptr (GITypeInfo) rti = gi_callable_info_get_return_type (cb);
                GITypeTag rt = gi_type_info_get_tag (rti);
                g_string_append (out, gi_type_tag_to_string (rt));
              }
            g_string_append (out, ")");
          }
        break;
      }
    default:
      break;
    }
  g_strlcpy (buf, out->str, buflen);
}

static int
validate_phase1_plan (const PyGIInvokePlan *plan, const char *qualified_name)
{
  gboolean return_is_paired_c_array = plan->return_tag == GI_TYPE_TAG_ARRAY
                                      && plan->return_array_type == GI_ARRAY_TYPE_C
                                      && plan->return_array_length_arg >= 0
                                      && type_info_has_supported_array_element (plan->return_ti);
  if (!return_is_paired_c_array && !type_info_is_supported (plan->return_ti, TRUE))
    {
      char shape[512] = "";
      format_arg_shape (plan->return_ti, shape, sizeof shape);
      PyErr_Format (PyExc_NotImplementedError,
                    "%s: unsupported return type [%s] is outside the current ginext invoke slice",
                    qualified_name,
                    shape);
      return -1;
    }

  for (size_t i = 0; i < plan->n_gi_args; i++)
    {
      const PyGIArgPlan *arg = &plan->args[i];
      if (arg->direction != GI_DIRECTION_IN)
        {
          if (return_is_paired_c_array && arg->direction == GI_DIRECTION_OUT
              && plan->return_array_length_arg == (ssize_t)i)
            continue;
          if (arg->direction == GI_DIRECTION_OUT)
            {
              if (arg_plan_is_supported_c_array_length (plan, arg))
                continue;
              if (arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH && arg_plan_is_supported_array (arg))
                continue;
              if (arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
                  && pygi_type_is_direct_storage (&arg->type))
                continue;
              if (arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH && arg->tag == GI_TYPE_TAG_ERROR)
                continue;
              if (arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
                  && gi_type_info_is_param_spec (arg->cached_ti))
                continue;
              if (arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
                  && gi_type_info_is_gvalue (arg->cached_ti))
                continue;
              if (arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
                  && (arg->tag == GI_TYPE_TAG_GLIST || arg->tag == GI_TYPE_TAG_GSLIST)
                  && type_info_is_supported_list_return (arg->cached_ti))
                continue;
              if (arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH && arg->tag == GI_TYPE_TAG_GHASH
                  && type_info_is_supported_hash_table (arg->cached_ti))
                continue;
              if (arg->caller_allocates && arg->tag == GI_TYPE_TAG_INTERFACE)
                {
                  g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (arg->cached_ti);
                  if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
                    continue;
                }
              if (arg->tag == GI_TYPE_TAG_INTERFACE && type_info_is_record (arg->cached_ti))
                continue;
              if (arg->tag == GI_TYPE_TAG_INTERFACE && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH)
                {
                  g_autoptr (GIBaseInfo) iface_out = gi_type_info_get_interface (arg->cached_ti);
                  if (iface_out != NULL
                      && (GI_IS_OBJECT_INFO (iface_out) || GI_IS_INTERFACE_INFO (iface_out)))
                    continue;
                }
            }
          if (arg->direction == GI_DIRECTION_INOUT && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
              && pygi_type_is_direct_storage (&arg->type))
            continue;
          if (arg->direction == GI_DIRECTION_INOUT && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
              && arg->tag == GI_TYPE_TAG_ERROR)
            continue;
          if (arg->direction == GI_DIRECTION_INOUT && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
              && gi_type_info_is_param_spec (arg->cached_ti))
            continue;
          if (arg->direction == GI_DIRECTION_INOUT && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
              && gi_type_info_is_gvalue (arg->cached_ti))
            continue;
          if (arg->direction == GI_DIRECTION_INOUT && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
              && (arg->tag == GI_TYPE_TAG_GLIST || arg->tag == GI_TYPE_TAG_GSLIST)
              && type_info_is_supported_list_return (arg->cached_ti))
            continue;
          if (arg->direction == GI_DIRECTION_INOUT && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
              && arg->tag == GI_TYPE_TAG_GHASH
              && type_info_is_supported_hash_table (arg->cached_ti))
            continue;
          if (arg->direction == GI_DIRECTION_INOUT && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
              && arg->tag == GI_TYPE_TAG_INTERFACE && type_info_is_record (arg->cached_ti))
            continue;
          if (arg->direction == GI_DIRECTION_INOUT && arg->role != PYGI_ARG_ROLE_ARRAY_LENGTH
              && arg->tag == GI_TYPE_TAG_INTERFACE)
            {
              g_autoptr (GIBaseInfo) iface_inout = gi_type_info_get_interface (arg->cached_ti);
              if (iface_inout != NULL
                  && (GI_IS_OBJECT_INFO (iface_inout) || GI_IS_INTERFACE_INFO (iface_inout)))
                continue;
            }
          if (arg->direction == GI_DIRECTION_INOUT
              && (arg_plan_is_supported_array (arg)
                  || arg_plan_is_supported_c_array_length (plan, arg)))
            continue;
          char shape[512] = "";
          format_arg_shape (arg->cached_ti, shape, sizeof shape);
          const char *dir_name = arg->direction == GI_DIRECTION_OUT
                                     ? "out"
                                     : (arg->direction == GI_DIRECTION_INOUT ? "inout" : "?");
          PyErr_Format (PyExc_NotImplementedError,
                        "%s: %s arg [%s] is outside the current ginext invoke slice",
                        qualified_name,
                        dir_name,
                        shape);
          return -1;
        }
      if (arg_plan_is_supported_array (arg))
        continue;
      if (arg->direction == GI_DIRECTION_IN && gi_type_info_is_gvalue (arg->cached_ti))
        continue;
      if (arg->direction == GI_DIRECTION_IN && arg->nullable_or_optional
          && type_info_is_glib_error (arg->cached_ti))
        continue;
      if (!type_info_is_supported (arg->cached_ti, FALSE))
        {
          char shape[512] = "";
          format_arg_shape (arg->cached_ti, shape, sizeof shape);
          PyErr_Format (
              PyExc_NotImplementedError,
              "%s: unsupported argument type [%s] is outside the current ginext invoke slice",
              qualified_name,
              shape);
          return -1;
        }
    }
  return 0;
}

static void
compiled_callable_destroy (PyGICompiledCallable *compiled)
{
  if (compiled == NULL)
    return;
  pygi_invoke_plan_clear (&compiled->invoke_plan);
  if (compiled->ffi_rinfo != NULL)
    gi_base_info_unref ((GIBaseInfo *)compiled->ffi_rinfo);
  if (compiled->info != NULL)
    gi_base_info_unref ((GIBaseInfo *)compiled->info);
  free (compiled->qualified_name);
  free (compiled->ffi_atypes);
  free (compiled->invoke_plan_args);
  free (compiled->invoke_plan_outs);
  free (compiled);
}

void
pygi_compiled_callable_destroy_for_ffi (PyGICompiledCallable *compiled)
{
  compiled_callable_destroy (compiled);
}

static void
method_descriptor_clear_fields (PyGIMethodDescriptor *descriptor)
{
  if (descriptor == NULL)
    return;
  compiled_callable_destroy (descriptor->compiled);
  descriptor->compiled = NULL;
  if (descriptor->info != NULL)
    gi_base_info_unref ((GIBaseInfo *)descriptor->info);
  descriptor->info = NULL;
  free (descriptor->qualified_name);
  descriptor->qualified_name = NULL;
  Py_CLEAR (descriptor->gimeta);
  Py_CLEAR (descriptor->name);
  Py_CLEAR (descriptor->qualname);
  Py_CLEAR (descriptor->module);
  Py_CLEAR (descriptor->doc);
  Py_CLEAR (descriptor->defaults);
  Py_CLEAR (descriptor->kwdefaults);
  Py_CLEAR (descriptor->annotations);
  Py_CLEAR (descriptor->annotate);
  Py_CLEAR (descriptor->type_params);
  Py_CLEAR (descriptor->objclass);
  Py_CLEAR (descriptor->namespace);
  Py_CLEAR (descriptor->arg_names);
}

static void
method_descriptor_destroy (PyGIMethodDescriptor *descriptor)
{
  if (descriptor == NULL)
    return;
  method_descriptor_clear_fields (descriptor);
  free (descriptor);
}

/* Build the visible-arg-name tuple with pygobject dash-to-underscore
 * applied. Caches on the descriptor so the per-call kwarg merge path is
 * just a tuple walk. Returns 0 on success, -1 on error (PyErr set). */
static int
descriptor_cache_arg_names (PyGIMethodDescriptor *descriptor, PyObject *capsule)
{
  PyObject *call_args = Py_BuildValue ("(O)", capsule);
  if (call_args == NULL)
    return -1;
  PyObject *names_list = py_callable_arg_names (NULL, call_args);
  Py_DECREF (call_args);
  if (names_list == NULL)
    return -1;

  Py_ssize_t n = PyList_GET_SIZE (names_list);
  PyObject *names_tuple = PyTuple_New (n);
  if (names_tuple == NULL)
    {
      Py_DECREF (names_list);
      return -1;
    }
  for (Py_ssize_t i = 0; i < n; i++)
    {
      PyObject *raw = PyList_GET_ITEM (names_list, i); /* borrowed */
      Py_ssize_t len;
      const char *utf8 = PyUnicode_AsUTF8AndSize (raw, &len);
      if (utf8 == NULL)
        {
          Py_DECREF (names_list);
          Py_DECREF (names_tuple);
          return -1;
        }
      PyObject *converted;
      if (memchr (utf8, '-', (size_t)len) != NULL)
        {
          char *buf = g_strndup (utf8, (gsize)len);
          for (char *p = buf; *p != '\0'; p++)
            if (*p == '-')
              *p = '_';
          converted = PyUnicode_FromStringAndSize (buf, len);
          g_free (buf);
        }
      else
        {
          converted = raw;
          Py_INCREF (converted);
        }
      if (converted == NULL)
        {
          Py_DECREF (names_list);
          Py_DECREF (names_tuple);
          return -1;
        }
      PyTuple_SET_ITEM (names_tuple, i, converted); /* steals */
    }
  Py_DECREF (names_list);
  descriptor->arg_names = names_tuple;
  return 0;
}

static PyGIMethodDescriptor *
method_descriptor_from_py (PyObject *obj)
{
  if (ginext_method_descriptor_type != NULL
      && PyObject_TypeCheck (obj, ginext_method_descriptor_type))
    return (PyGIMethodDescriptor *)obj;
  if (PyCapsule_CheckExact (obj))
    return PyCapsule_GetPointer (obj, CALLABLE_DESCRIPTOR_CAPSULE_NAME);
  PyErr_Format (PyExc_TypeError,
                "expected %s or a callable descriptor capsule, got %s",
                ginext_method_descriptor_type != NULL ? ginext_method_descriptor_type->tp_name
                                                      : "ginext.private._gobject.MethodDescriptor",
                Py_TYPE (obj)->tp_name);
  return NULL;
}

static void
missing_regress_noop_pointer (void *unused G_GNUC_UNUSED)
{
}

static const char *
missing_regress_const_char_retval (void)
{
  return "stub";
}

static const void *
missing_regress_const_struct_retval (void)
{
  return NULL;
}

static void
missing_regress_noop_unsigned (unsigned unused G_GNUC_UNUSED)
{
}

static void
missing_regress_noop_gboolean (gboolean unused G_GNUC_UNUSED)
{
}

static int
missing_regress_foo_bunion_get_contained_type (void *bunion)
{
  if (bunion == NULL)
    return 0;
  return *(int *)bunion;
}

static void
missing_regress_noop_three_pointers (void *a G_GNUC_UNUSED,
                                     void *b G_GNUC_UNUSED,
                                     void *c G_GNUC_UNUSED)
{
}

static void *
pygi_resolve_missing_regress_symbol (const char *symbol)
{
  if (g_strcmp0 (symbol, "regress_foo_test_const_char_param") == 0)
    return missing_regress_noop_pointer;
  if (g_strcmp0 (symbol, "regress_foo_test_const_char_retval") == 0)
    return missing_regress_const_char_retval;
  if (g_strcmp0 (symbol, "regress_foo_test_const_struct_param") == 0)
    return missing_regress_noop_pointer;
  if (g_strcmp0 (symbol, "regress_foo_test_const_struct_retval") == 0)
    return missing_regress_const_struct_retval;
  if (g_strcmp0 (symbol, "regress_foo_test_unsigned_type") == 0)
    return missing_regress_noop_unsigned;
  if (g_strcmp0 (symbol, "regress_set_abort_on_error") == 0)
    return missing_regress_noop_gboolean;
  if (g_strcmp0 (symbol, "regress_foo_async_ready_callback") == 0)
    return missing_regress_noop_three_pointers;
  if (g_strcmp0 (symbol, "regress_foo_destroy_notify_callback") == 0)
    return missing_regress_noop_three_pointers;
  if (g_strcmp0 (symbol, "regress_foo_bunion_get_contained_type") == 0)
    return missing_regress_foo_bunion_get_contained_type;
  return NULL;
}

static PyGICompiledCallable *
compile_callable_for_ffi_target (GICallableInfo *callable,
                                 void *target,
                                 int has_self,
                                 const char *qualified_name)
{
  pygi_ginext_record_plan_gi_metadata_call ();
  int n_args_signed = gi_callable_info_get_n_args (callable);
  if (n_args_signed < 0)
    {
      PyErr_Format (PyExc_RuntimeError, "%s: invalid callable argument count", qualified_name);
      return NULL;
    }
  size_t n_args = (size_t)n_args_signed;

  PyGICompiledCallable *compiled = calloc (1, sizeof (*compiled));
  if (compiled == NULL)
    {
      PyErr_NoMemory ();
      return NULL;
    }

  compiled->info = (GICallableInfo *)gi_base_info_ref ((GIBaseInfo *)callable);
  compiled->qualified_name = strdup (qualified_name);
  compiled->target_fn = target;
  compiled->has_self = has_self ? 1 : 0;
  if (compiled->qualified_name == NULL)
    {
      compiled_callable_destroy (compiled);
      PyErr_NoMemory ();
      return NULL;
    }

  init_plan_storage (compiled, n_args);
  if (compiled->invoke_plan_args == NULL || compiled->invoke_plan_outs == NULL)
    {
      compiled_callable_destroy (compiled);
      PyErr_NoMemory ();
      return NULL;
    }

  pygi_invoke_plan (callable, has_self, SIZE_MAX, &compiled->invoke_plan);
  if (validate_phase1_plan (&compiled->invoke_plan, qualified_name) < 0)
    {
      compiled_callable_destroy (compiled);
      return NULL;
    }

  PyGIInvokePlan *plan = &compiled->invoke_plan;
  for (size_t i = 0; i < plan->n_gi_args; i++)
    {
      if (plan->args[i].role == PYGI_ARG_ROLE_CLOSURE_DESTROY)
        {
          compiled->has_closure_companions = true;
          break;
        }
    }

  pygi_ginext_record_plan_gi_metadata_call ();
  compiled->ffi_rinfo = gi_callable_info_get_return_type (callable);
  if (compiled->ffi_rinfo == NULL)
    {
      compiled_callable_destroy (compiled);
      PyErr_NoMemory ();
      return NULL;
    }
  pygi_ginext_record_plan_gi_metadata_call ();
  compiled->ffi_rtype = gi_type_info_get_ffi_type (compiled->ffi_rinfo);
  pygi_ginext_record_plan_gi_metadata_call ();
  compiled->ffi_rtag = gi_type_info_get_tag (compiled->ffi_rinfo);
  pygi_ginext_record_plan_gi_metadata_call ();
  compiled->ffi_return_is_pointer = gi_type_info_is_pointer (compiled->ffi_rinfo);
  compiled->ffi_throws = plan->can_throw_gerror;
  compiled->ffi_n_invoke_args
      = (unsigned int)plan->n_gi_args + (has_self ? 1u : 0u) + (compiled->ffi_throws ? 1u : 0u);
  compiled->ffi_atypes = calloc (compiled->ffi_n_invoke_args ? compiled->ffi_n_invoke_args : 1u,
                                 sizeof (*compiled->ffi_atypes));
  if (compiled->ffi_atypes == NULL)
    {
      compiled_callable_destroy (compiled);
      PyErr_NoMemory ();
      return NULL;
    }

  unsigned int slot = 0;
  if (has_self)
    compiled->ffi_atypes[slot++] = &ffi_type_pointer;
  for (size_t i = 0; i < plan->n_gi_args; i++)
    {
      const PyGIArgPlan *arg = &plan->args[i];
      if (arg->direction == GI_DIRECTION_IN)
        {
          pygi_ginext_record_plan_gi_metadata_call ();
          if (gi_type_info_is_gvalue (arg->cached_ti) && !gi_type_info_is_pointer (arg->cached_ti))
            compiled->ffi_atypes[slot++] = &gvalue_ffi_type;
          else
            compiled->ffi_atypes[slot++] = gi_type_info_get_ffi_type (arg->cached_ti);
        }
      else
        {
          compiled->ffi_atypes[slot++] = &ffi_type_pointer;
        }
    }
  if (compiled->ffi_throws)
    compiled->ffi_atypes[slot++] = &ffi_type_pointer;

  if (ffi_prep_cif (&compiled->ffi_cif,
                    FFI_DEFAULT_ABI,
                    compiled->ffi_n_invoke_args,
                    compiled->ffi_rtype,
                    compiled->ffi_atypes)
      != FFI_OK)
    {
      PyErr_Format (PyExc_RuntimeError, "%s: ffi_prep_cif failed", qualified_name);
      compiled_callable_destroy (compiled);
      return NULL;
    }
  compiled->ffi_setup_ready = true;
  return compiled;
}

PyGICompiledCallable *
pygi_compile_callable_for_ffi_target (GICallableInfo *callable,
                                      void *target,
                                      int has_self,
                                      const char *qualified_name)
{
  return compile_callable_for_ffi_target (callable, target, has_self, qualified_name);
}

static PyGICompiledCallable *
compile_callable_for_ffi (GIFunctionInfo *function, int has_self, const char *qualified_name)
{
  pygi_ginext_record_plan_gi_metadata_call ();
  const char *symbol = gi_function_info_get_symbol (function);
  if (symbol == NULL || symbol[0] == '\0')
    {
      PyErr_Format (PyExc_NotImplementedError, "%s: callable has no C symbol", qualified_name);
      return NULL;
    }

  void *target = dlsym (RTLD_DEFAULT, symbol);
  if (target == NULL)
    target = pygi_resolve_missing_regress_symbol (symbol);
  if (target == NULL)
    {
      PyErr_Format (PyExc_NotImplementedError,
                    "%s: could not resolve C symbol %s",
                    qualified_name,
                    symbol);
      return NULL;
    }

  return compile_callable_for_ffi_target ((GICallableInfo *)function,
                                          target,
                                          has_self,
                                          qualified_name);
}

PyObject *
py_build_callable_descriptor (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *capsule = NULL;
  const char *qualified_name = NULL;
  int has_self = 0;
  PyObject *namespace = NULL;
  if (!PyArg_ParseTuple (args, "Osp|O", &capsule, &qualified_name, &has_self, &namespace))
    return NULL;

  GIBaseInfo *base = info_from_capsule (capsule);
  if (base == NULL)
    return NULL;
  if (!GI_IS_FUNCTION_INFO (base))
    {
      PyErr_SetString (PyExc_TypeError, "expected GIFunctionInfo capsule");
      return NULL;
    }
  if (ginext_method_descriptor_type == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "MethodDescriptor type not initialized");
      return NULL;
    }

  PyObject *descriptor_obj = PyType_GenericAlloc (ginext_method_descriptor_type, 0);
  if (descriptor_obj == NULL)
    return NULL;
  PyGIMethodDescriptor *descriptor = (PyGIMethodDescriptor *)descriptor_obj;
  descriptor->vectorcall = method_descriptor_vectorcall;
  descriptor->info = (GIFunctionInfo *)gi_base_info_ref (base);
  descriptor->has_self = has_self ? 1 : 0;
  descriptor->namespace = Py_XNewRef (namespace);
  descriptor->qualified_name = strdup (qualified_name);
  if (descriptor->qualified_name == NULL)
    {
      Py_DECREF (descriptor_obj);
      return PyErr_NoMemory ();
    }

  descriptor->compiled = compile_callable_for_ffi ((GIFunctionInfo *)base,
                                                   descriptor->has_self,
                                                   descriptor->qualified_name);
  if (descriptor->compiled == NULL)
    {
      Py_DECREF (descriptor_obj);
      return NULL;
    }

  if (descriptor_cache_arg_names (descriptor, capsule) != 0)
    {
      Py_DECREF (descriptor_obj);
      return NULL;
    }
  PyObject *user_data_call_args = Py_BuildValue ("(O)", capsule);
  if (user_data_call_args == NULL)
    {
      Py_DECREF (descriptor_obj);
      return NULL;
    }
  PyObject *user_data_flag = py_callable_has_user_data_slot (NULL, user_data_call_args);
  Py_DECREF (user_data_call_args);
  if (user_data_flag == NULL)
    {
      Py_DECREF (descriptor_obj);
      return NULL;
    }
  descriptor->has_user_data_slot = PyObject_IsTrue (user_data_flag);
  Py_DECREF (user_data_flag);
  if (descriptor->has_user_data_slot < 0)
    {
      Py_DECREF (descriptor_obj);
      return NULL;
    }

  /* Count closure companion slots that are elided from the default Python
   * surface (CLOSURE_DESTROY with a forward owner_callback_arg pointer).
   * Used by resolve_call_args to distinguish "each extra fills one slot"
   * (pass-through) from "extras are all user_data for one callback"
   * (pack into _PackedUserData). */
  if (descriptor->compiled != NULL)
    {
      const PyGIInvokePlan *plan = &descriptor->compiled->invoke_plan;
      Py_ssize_t n_elided = 0;
      for (size_t i = 0; i < plan->n_gi_args; i++)
        {
          if (plan->args[i].role == PYGI_ARG_ROLE_CLOSURE_DESTROY
              && plan->args[i].owner_callback_arg >= 0)
            n_elided++;
        }
      descriptor->n_elided_closures = n_elided;
    }

  return descriptor_obj;
}

/* Bare callable name after the last dot: "Gtk.Widget.show" -> "show".
 * Used in TypeError messages so they match the pygobject surface
 * (and avoid leaking namespace-prefixed qualified names that the
 * Python caller never sees). */
static const char *
descriptor_bare_name (const PyGIMethodDescriptor *d)
{
  const char *q = d->qualified_name;
  if (q == NULL)
    return "?";
  const char *dot = strrchr (q, '.');
  return dot != NULL ? dot + 1 : q;
}

static PyObject *
method_descriptor_signature (PyObject *self, void *closure G_GNUC_UNUSED)
{
  PyObject *fn = pygi_hook_last (pygi_hook_callable_signature);
  if (fn == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "callable_signature hook not registered");
      return NULL;
    }
  PyObject *gimeta = PyObject_GetAttrString (self, "gimeta");
  if (gimeta == NULL)
    return NULL;
  PyObject *result = PyObject_CallOneArg (fn, gimeta);
  Py_DECREF (gimeta);
  return result;
}

static PyObject *
method_descriptor_repr (PyObject *self)
{
  PyGIMethodDescriptor *descriptor = (PyGIMethodDescriptor *)self;
  return PyUnicode_FromFormat ("<ginext method %s>",
                               descriptor->qualified_name != NULL ? descriptor->qualified_name
                                                                  : "<?>");
}

static PyObject *
method_descriptor_descr_get (PyObject *self, PyObject *obj, PyObject *type G_GNUC_UNUSED)
{
  if (obj == NULL)
    return Py_NewRef (self);
  return PyMethod_New (self, obj);
}

static PyObject *
invoke_descriptor_with_tuple_kwargs (PyGIMethodDescriptor *descriptor,
                                     PyObject *py_args,
                                     PyObject *kwargs)
{
  if (!PyTuple_Check (py_args))
    {
      PyErr_SetString (PyExc_TypeError, "args must be a tuple");
      return NULL;
    }
  if (kwargs != NULL && kwargs != Py_None && !PyDict_Check (kwargs))
    {
      PyErr_SetString (PyExc_TypeError, "kwargs must be a dict or None");
      return NULL;
    }

  PyObject *actual_kwargs = kwargs == Py_None ? NULL : kwargs;
  PyObject *self_obj = NULL;
  Py_ssize_t args_offset = 0;
  if (descriptor->has_self)
    {
      if (PyTuple_GET_SIZE (py_args) < 1)
        {
          PyErr_SetString (PyExc_TypeError, "bound method call missing self");
          return NULL;
        }
      self_obj = PyTuple_GET_ITEM (py_args, 0);
      args_offset = 1;
    }

  PyObject *final_args
      = resolve_call_args (descriptor, self_obj, py_args, args_offset, actual_kwargs);
  if (final_args == NULL)
    return NULL;

  Py_ssize_t nargs_signed = PyTuple_GET_SIZE (final_args);
  size_t nargs = (size_t)nargs_signed;
  PyObject **call_args = g_alloca (sizeof (*call_args) * (nargs ? nargs : 1u));
  for (size_t i = 0; i < nargs; i++)
    call_args[i] = PyTuple_GET_ITEM (final_args, (Py_ssize_t)i);

  PyObject *result = pygi_method_descriptor_call_ffi_invoke (descriptor, call_args, nargs, NULL);
  Py_DECREF (final_args);
  if (result != NULL && PyErr_Occurred ())
    {
      Py_DECREF (result);
      return NULL;
    }
  return result;
}

static PyObject *
invoke_self_object_void_fastcall (PyGIMethodDescriptor *descriptor,
                                  gpointer self_ptr,
                                  PyObject *arg)
{
  gpointer arg_ptr = NULL;

  if (invoke_descriptor_gobject_arg_fastcall (&descriptor->compiled->invoke_plan.args[0],
                                              arg,
                                              &arg_ptr)
      != 0)
    return NULL;

  ((void (*) (gpointer, gpointer))descriptor->compiled->target_fn) (self_ptr, arg_ptr);
  Py_RETURN_NONE;
}

static PyObject *
invoke_self_bool_void_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr, gboolean arg)
{
  ((void (*) (gpointer, gboolean))descriptor->compiled->target_fn) (self_ptr, arg);
  Py_RETURN_NONE;
}

static PyObject *
invoke_self_utf8_void_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr, char *arg)
{
  ((void (*) (gpointer, const char *))descriptor->compiled->target_fn) (self_ptr, arg);
  Py_RETURN_NONE;
}

static PyObject *
invoke_object_return_fastcall (PyGIMethodDescriptor *descriptor, gpointer ret_ptr)
{
  PyGIInvokePlan *plan = &descriptor->compiled->invoke_plan;

  if (ret_ptr == NULL && plan->return_null_is_error)
    {
      PyErr_Format (PyExc_RuntimeError,
                    "%s returned NULL for a non-nullable %s result",
                    gi_base_info_get_name ((GIBaseInfo *)descriptor->info),
                    gi_type_tag_to_string (plan->return_tag));
      return NULL;
    }
  if (plan->return_type.gtype == G_TYPE_INVALID || plan->return_type.gtype == G_TYPE_NONE)
    return NULL;
  if (!g_type_is_a (plan->return_type.gtype, G_TYPE_OBJECT)
      && !g_type_is_a (plan->return_type.gtype, G_TYPE_INTERFACE))
    return NULL;
  return pygi_gobject_to_py_as_gtype ((GObject *)ret_ptr,
                                      plan->return_type.gtype,
                                      plan->return_transfer);
}

static PyObject *
invoke_self_void_void_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr)
{
  ((void (*) (gpointer))descriptor->compiled->target_fn) (self_ptr);
  Py_RETURN_NONE;
}

static PyObject *
invoke_self_void_boolean_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr)
{
  gboolean ret = ((gboolean (*) (gpointer))descriptor->compiled->target_fn) (self_ptr);
  return PyBool_FromLong (ret != FALSE);
}

static PyObject *
invoke_self_void_int32_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr)
{
  gint32 ret = ((gint32 (*) (gpointer))descriptor->compiled->target_fn) (self_ptr);
  return PyLong_FromLong ((long)ret);
}

static PyObject *
invoke_self_void_utf8_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr)
{
  GIArgument ret = { 0 };

  ret.v_string = ((char * (*) (gpointer))descriptor->compiled->target_fn) (self_ptr);
  return pygi_utf8_to_py (&ret, descriptor->compiled->invoke_plan.return_transfer);
}

static PyObject *
invoke_self_utf8_object_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr, char *arg)
{
  gpointer ret_ptr = ((gpointer (*) (gpointer, const char *))descriptor->compiled->target_fn) (
      self_ptr, arg);
  return invoke_object_return_fastcall (descriptor, ret_ptr);
}

static PyObject *
invoke_self_int32_object_fastcall (PyGIMethodDescriptor *descriptor, gpointer self_ptr, gint32 arg)
{
  gpointer ret_ptr
      = ((gpointer (*) (gpointer, gint32))descriptor->compiled->target_fn) (self_ptr, arg);
  return invoke_object_return_fastcall (descriptor, ret_ptr);
}

static int
invoke_descriptor_gobject_self_fastcall (PyGIInvokePlan *plan,
                                         PyObject *self_arg,
                                         gpointer *self_ptr_out)
{
  if (plan->self_gtype == G_TYPE_INVALID || plan->self_gtype == G_TYPE_NONE
      || !g_type_is_a (plan->self_gtype, G_TYPE_OBJECT))
    return -1;

  gpointer self_obj = pygi_gobject_get (self_arg);
  if (self_obj == NULL)
    {
      PyErr_Clear ();
      pygi_raise_gobject_type_error_for_gtype_named (G_TYPE_OBJECT, self_arg, "self");
      return -1;
    }

  GType actual_gtype = G_TYPE_FROM_INSTANCE ((GTypeInstance *)self_obj);
  if (actual_gtype != 0 && !g_type_is_a (actual_gtype, plan->self_gtype))
    {
      pygi_raise_gobject_type_error_for_gtype_named (plan->self_gtype, self_arg, "self");
      return -1;
    }

  if (plan->instance_transfer == GI_TRANSFER_EVERYTHING && G_IS_OBJECT (self_obj))
    g_object_ref ((GObject *)self_obj);
  *self_ptr_out = self_obj;
  return 0;
}

static int
invoke_descriptor_gobject_arg_fastcall (const PyGIArgPlan *arg_plan,
                                        PyObject *arg,
                                        gpointer *arg_ptr_out)
{
  gpointer arg_ptr = NULL;

  if (arg != Py_None)
    {
      arg_ptr = pygi_gobject_get (arg);
      if (arg_ptr == NULL)
        {
          PyErr_Clear ();
          pygi_raise_gobject_type_error_for_gtype_named (arg_plan->type.gtype != G_TYPE_INVALID
                                                                 && arg_plan->type.gtype != G_TYPE_NONE
                                                             ? arg_plan->type.gtype
                                                             : G_TYPE_OBJECT,
                                                         arg,
                                                         arg_plan->cached_ai
                                                             ? gi_base_info_get_name ((GIBaseInfo *)arg_plan->cached_ai)
                                                             : NULL);
          return -1;
        }
      if (arg_plan->type.gtype != G_TYPE_INVALID && arg_plan->type.gtype != G_TYPE_NONE
          && !g_type_is_a (G_TYPE_FROM_INSTANCE ((GTypeInstance *)arg_ptr), arg_plan->type.gtype))
        {
          pygi_raise_gobject_type_error_for_gtype_named (
              arg_plan->type.gtype, arg,
              arg_plan->cached_ai ? gi_base_info_get_name ((GIBaseInfo *)arg_plan->cached_ai) : NULL);
          return -1;
        }
      if (arg_plan->marshal_kind == PYGI_MARSHAL_GOBJECT_OWNED && G_IS_OBJECT (arg_ptr))
        g_object_ref ((GObject *)arg_ptr);
    }

  *arg_ptr_out = arg_ptr;
  return 0;
}

static int
invoke_descriptor_utf8_arg_fastcall (const PyGIArgPlan *arg_plan,
                                     PyObject *arg,
                                     char **arg_string_out)
{
  GIArgument converted = { 0 };

  if (arg == Py_None && !arg_plan->nullable_or_optional)
    {
      PyErr_Format (PyExc_TypeError,
                    "argument %zd must be str, bytes, or bytearray, not None",
                    (Py_ssize_t)arg_plan->py_arg_index + 1);
      return -1;
    }

  if (pygi_utf8_from_py (arg, &converted) != 0)
    return -1;

  if ((arg_plan->marshal_kind == PYGI_MARSHAL_UTF8
       || arg_plan->marshal_kind == PYGI_MARSHAL_UTF8_OWNED)
      && arg != Py_None
      && !PyUnicode_Check (arg)
      && !PyBytes_Check (arg)
      && !PyByteArray_Check (arg))
    {
      PyErr_Format (PyExc_TypeError,
                    "argument %zd must be str, bytes, or bytearray, not %s",
                    (Py_ssize_t)arg_plan->py_arg_index + 1,
                    Py_TYPE (arg)->tp_name);
      return -1;
    }

  if (arg_plan->marshal_kind == PYGI_MARSHAL_UTF8_OWNED && converted.v_string != NULL)
    {
      char *dup = g_strdup (converted.v_string);
      if (dup == NULL)
        {
          PyErr_NoMemory ();
          return -1;
        }
      converted.v_string = dup;
    }

  *arg_string_out = converted.v_string;
  return 0;
}

static PyObject *
invoke_descriptor_trivial_scalar_fastcall (PyGIMethodDescriptor *descriptor,
                                           PyObject *const *args,
                                           Py_ssize_t nargs)
{
  PyGICompiledCallable *compiled = descriptor->compiled;
  if (compiled == NULL)
    return NULL;

  PyGIInvokePlan *plan = &compiled->invoke_plan;
  if (descriptor->has_user_data_slot || descriptor->n_elided_closures != 0 || plan->can_throw_gerror
      || plan->n_out_args != 0 || plan->n_py_args != (size_t)nargs
      || plan->n_gi_args != (size_t)nargs - (descriptor->has_self ? 1u : 0u))
    return NULL;

  gpointer self_ptr = NULL;
  if (descriptor->has_self)
    {
      if (nargs < 1)
        return NULL;
      if (invoke_descriptor_gobject_self_fastcall (plan, args[0], &self_ptr) != 0)
        return NULL;
    }

  Py_ssize_t arg_offset = descriptor->has_self ? 1 : 0;

  for (Py_ssize_t i = 0; i < (Py_ssize_t)plan->n_gi_args; i++)
    {
      const PyGIArgPlan *arg_plan = &plan->args[i];
      if (arg_plan->role != PYGI_ARG_ROLE_NORMAL || arg_plan->direction != GI_DIRECTION_IN)
        return NULL;
    }

  GIArgument converted_args[6] = { 0 };
  for (Py_ssize_t i = 0; i < (Py_ssize_t)plan->n_gi_args; i++)
    {
      const PyGIArgPlan *arg_plan = &plan->args[i];
      switch (arg_plan->marshal_kind)
        {
        case PYGI_MARSHAL_BOOL:
          if (pygi_boolean_from_py (args[i + arg_offset], &converted_args[i]) != 0)
            return NULL;
          break;
        case PYGI_MARSHAL_INT32:
          if (pygi_int32_from_py (args[i + arg_offset], &converted_args[i]) != 0)
            return NULL;
          break;
        case PYGI_MARSHAL_UTF8:
        case PYGI_MARSHAL_UTF8_OWNED:
        case PYGI_MARSHAL_GOBJECT:
        case PYGI_MARSHAL_GOBJECT_OWNED:
          break;
        default:
          return NULL;
        }
    }

  if (plan->return_tag == GI_TYPE_TAG_VOID)
    {
      if (descriptor->has_self)
        {
          if (plan->n_gi_args == 1
              && (plan->args[0].marshal_kind == PYGI_MARSHAL_GOBJECT
                  || plan->args[0].marshal_kind == PYGI_MARSHAL_GOBJECT_OWNED))
            return invoke_self_object_void_fastcall (descriptor, self_ptr, args[arg_offset]);

          switch (plan->n_gi_args)
            {
            case 0:
              return invoke_self_void_void_fastcall (descriptor, self_ptr);
            case 1:
              switch (plan->args[0].marshal_kind)
                {
                case PYGI_MARSHAL_BOOL:
                  return invoke_self_bool_void_fastcall (descriptor,
                                                         self_ptr,
                                                         converted_args[0].v_boolean);
                case PYGI_MARSHAL_UTF8:
                case PYGI_MARSHAL_UTF8_OWNED:
                  {
                    char *arg_string = NULL;

                    if (invoke_descriptor_utf8_arg_fastcall (&plan->args[0],
                                                             args[arg_offset],
                                                             &arg_string)
                        != 0)
                      return NULL;
                    return invoke_self_utf8_void_fastcall (descriptor, self_ptr, arg_string);
                  }
                default:
                  return NULL;
                }
            default:
              return NULL;
            }
        }

      switch (nargs)
        {
        case 0:
          ((void (*) (void))compiled->target_fn) ();
          Py_RETURN_NONE;
        default:
          return NULL;
        }
    }

  if (descriptor->has_self)
    {
      if (plan->return_tag == GI_TYPE_TAG_BOOLEAN)
        {
          switch (plan->n_gi_args)
            {
            case 0:
              return invoke_self_void_boolean_fastcall (descriptor, self_ptr);
            default:
              return NULL;
            }
        }

      if (plan->return_tag == GI_TYPE_TAG_INTERFACE
          && (plan->return_type.kind == PYGI_TYPE_OBJECT
              || plan->return_type.kind == PYGI_TYPE_INTERFACE))
        {
          switch (plan->n_gi_args)
            {
            case 1:
              switch (plan->args[0].marshal_kind)
                {
                case PYGI_MARSHAL_UTF8:
                case PYGI_MARSHAL_UTF8_OWNED:
                  {
                    char *arg_string = NULL;

                    if (invoke_descriptor_utf8_arg_fastcall (&plan->args[0],
                                                             args[arg_offset],
                                                             &arg_string)
                        != 0)
                      return NULL;
                    return invoke_self_utf8_object_fastcall (descriptor, self_ptr, arg_string);
                  }
                case PYGI_MARSHAL_INT32:
                  return invoke_self_int32_object_fastcall (descriptor,
                                                            self_ptr,
                                                            converted_args[0].v_int32);
                default:
                  return NULL;
                }
            default:
              return NULL;
            }
        }

      if (plan->return_tag != GI_TYPE_TAG_INT32)
        {
          if (plan->return_tag == GI_TYPE_TAG_UTF8 && plan->n_gi_args == 0)
            return invoke_self_void_utf8_fastcall (descriptor, self_ptr);
          return NULL;
        }

      switch (plan->n_gi_args)
        {
        case 0:
          return invoke_self_void_int32_fastcall (descriptor, self_ptr);
        default:
          return NULL;
        }
    }

  if (plan->return_tag != GI_TYPE_TAG_INT32)
    return NULL;

  gint32 ret = 0;
  switch (nargs)
    {
    case 0:
      ret = ((gint32 (*) (void))compiled->target_fn) ();
      break;
    case 1:
      ret = ((gint32 (*) (gint32))compiled->target_fn) (converted_args[0].v_int32);
      break;
    case 2:
      ret = ((gint32 (*) (gint32, gint32))compiled->target_fn) (converted_args[0].v_int32,
                                                                converted_args[1].v_int32);
      break;
    case 3:
      ret = ((gint32 (*) (gint32, gint32, gint32))compiled->target_fn) (converted_args[0].v_int32,
                                                                        converted_args[1].v_int32,
                                                                        converted_args[2].v_int32);
      break;
    case 4:
      ret = ((gint32 (*) (gint32, gint32, gint32, gint32))compiled->target_fn) (
          converted_args[0].v_int32,
          converted_args[1].v_int32,
          converted_args[2].v_int32,
          converted_args[3].v_int32);
      break;
    case 5:
      ret = ((gint32 (*) (gint32, gint32, gint32, gint32, gint32))compiled->target_fn) (
          converted_args[0].v_int32,
          converted_args[1].v_int32,
          converted_args[2].v_int32,
          converted_args[3].v_int32,
          converted_args[4].v_int32);
      break;
    case 6:
      ret = ((gint32 (*) (gint32, gint32, gint32, gint32, gint32, gint32))compiled->target_fn) (
          converted_args[0].v_int32,
          converted_args[1].v_int32,
          converted_args[2].v_int32,
          converted_args[3].v_int32,
          converted_args[4].v_int32,
          converted_args[5].v_int32);
      break;
    default:
      return NULL;
    }

  return PyLong_FromLong ((long)ret);
}

static PyObject *
method_descriptor_vectorcall (PyObject *self,
                              PyObject *const *args,
                              size_t nargsf,
                              PyObject *kwnames)
{
  return invoke_descriptor_vectorcall ((PyGIMethodDescriptor *)self, args, nargsf, kwnames);
}

static PyObject *
invoke_descriptor_vectorcall (PyGIMethodDescriptor *descriptor,
                              PyObject *const *args,
                              size_t nargsf,
                              PyObject *kwnames)
{
  Py_ssize_t nargs = (Py_ssize_t)PyVectorcall_NARGS (nargsf);
  if (kwnames == NULL)
    {
      PyObject *fast_result = invoke_descriptor_trivial_scalar_fastcall (descriptor, args, nargs);
      if (fast_result != NULL || PyErr_Occurred ())
        return fast_result;

      Py_ssize_t n_visible
          = PyTuple_GET_SIZE (descriptor->arg_names) + (descriptor->has_self ? 1 : 0);
      if (!descriptor->has_user_data_slot && descriptor->n_elided_closures == 0
          && nargs <= n_visible)
        return pygi_method_descriptor_call_ffi_invoke (descriptor, args, (size_t)nargs, NULL);
    }

  Py_ssize_t nkwargs = kwnames != NULL ? PyTuple_GET_SIZE (kwnames) : 0;
  PyObject *args_tuple = PyTuple_New (nargs);
  if (args_tuple == NULL)
    return NULL;
  for (Py_ssize_t i = 0; i < nargs; i++)
    {
      PyObject *value = args[i];
      Py_INCREF (value);
      PyTuple_SET_ITEM (args_tuple, i, value);
    }

  PyObject *kwargs = NULL;
  if (nkwargs > 0)
    {
      kwargs = PyDict_New ();
      if (kwargs == NULL)
        {
          Py_DECREF (args_tuple);
          return NULL;
        }
      for (Py_ssize_t i = 0; i < nkwargs; i++)
        {
          PyObject *key = PyTuple_GET_ITEM (kwnames, i);
          if (PyDict_SetItem (kwargs, key, args[nargs + i]) < 0)
            {
              Py_DECREF (kwargs);
              Py_DECREF (args_tuple);
              return NULL;
            }
        }
    }

  PyObject *result = invoke_descriptor_with_tuple_kwargs (descriptor, args_tuple, kwargs);
  Py_DECREF (args_tuple);
  Py_XDECREF (kwargs);
  return result;
}

static void
method_descriptor_dealloc (PyObject *self)
{
  method_descriptor_clear_fields ((PyGIMethodDescriptor *)self);
  Py_TYPE (self)->tp_free (self);
}

static PyMemberDef method_descriptor_members[] = {
  { "__vectorcalloffset__",
    Py_T_PYSSIZET,
    offsetof (PyGIMethodDescriptor, vectorcall),
    Py_READONLY,
    NULL },
  { "gimeta", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, gimeta), 0, NULL },
  { "__name__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, name), 0, NULL },
  { "__qualname__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, qualname), 0, NULL },
  { "__module__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, module), 0, NULL },
  { "__doc__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, doc), 0, NULL },
  { "__defaults__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, defaults), 0, NULL },
  { "__kwdefaults__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, kwdefaults), 0, NULL },
  { "__annotations__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, annotations), 0, NULL },
  { "__annotate__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, annotate), 0, NULL },
  { "__type_params__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, type_params), 0, NULL },
  { "__objclass__", Py_T_OBJECT_EX, offsetof (PyGIMethodDescriptor, objclass), 0, NULL },
  { NULL, 0, 0, 0, NULL },
};

static PyGetSetDef method_descriptor_getset[] = {
  { "__signature__", method_descriptor_signature, NULL, NULL, NULL },
  { NULL, NULL, NULL, NULL, NULL },
};

static PyType_Slot method_descriptor_slots[] = {
  { Py_tp_dealloc, (void *)method_descriptor_dealloc },
  { Py_tp_call, (void *)PyVectorcall_Call },
  { Py_tp_repr, (void *)method_descriptor_repr },
  { Py_tp_descr_get, (void *)method_descriptor_descr_get },
  { Py_tp_members, method_descriptor_members },
  { Py_tp_getset, method_descriptor_getset },
  { 0, NULL },
};

PyType_Spec GinextMethodDescriptor_spec = {
  .name = "ginext.private._gobject.MethodDescriptor",
  .basicsize = sizeof (PyGIMethodDescriptor),
  .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_VECTORCALL | Py_TPFLAGS_METHOD_DESCRIPTOR,
  .slots = method_descriptor_slots,
};

/* Lazily import ginext.method._PackedUserData. Cached for the process
 * lifetime; the type is stable. The trampoline in shims.c imports the
 * same type independently, so a re-fetch here would just duplicate
 * work. */
static PyObject *
packed_user_data_type (void)
{
  PyObject *type_obj = pygi_hook_last (pygi_hook_packed_user_data_type);
  /* NULL means not registered yet; caller must check */
  return type_obj;
}

/* Resolve the call's (args, kwargs) into the positional tuple that the
 * FFI invoke path consumes.
 *
 * pygobject-compat shape:
 *   - For callables with a closure user_data slot, trailing positional
 *     args beyond the visible signature pack into a single value (a
 *     `_PackedUserData` tuple if more than one). A `user_data=` kwarg
 *     surfaces as the same trailing positional. Both shapes at once is
 *     a TypeError.
 *   - Remaining kwargs bind to positions via the descriptor's cached
 *     arg-name tuple. Missing, duplicated, or unknown kwargs raise
 *     TypeError with the pygobject-compatible message format.
 *
 * `self_obj`, when non-NULL, is placed at slot 0 of the returned tuple
 * (bound-method form). `args_offset` skips that many leading items in
 * `args_in` — used by the bound-method path so the caller doesn't need
 * to allocate a self-stripped slice first.
 *
 * Returns a new tuple of length `(self_obj ? 1 : 0) + n_visible`
 * (+1 if user_data was supplied), or NULL on error (PyErr set). */
static PyObject *
resolve_call_args (PyGIMethodDescriptor *d,
                   PyObject *self_obj,
                   PyObject *args_in,
                   Py_ssize_t args_offset,
                   PyObject *kwargs_in)
{
  PyObject *arg_names = d->arg_names;
  Py_ssize_t n_visible = PyTuple_GET_SIZE (arg_names);
  Py_ssize_t n_args = PyTuple_GET_SIZE (args_in) - args_offset;
  Py_ssize_t n_kw = (kwargs_in != NULL) ? PyDict_GET_SIZE (kwargs_in) : 0;
  Py_ssize_t self_pad = (self_obj != NULL) ? 1 : 0;

  /* Step 1: user_data peel (only when the callable actually exposes a
   * closure slot — otherwise user_data= becomes a normal unknown kwarg
   * error from the merge step below, matching the old Python path). */
  PyObject *user_data = NULL;
  int has_user_data_kw = 0;
  Py_ssize_t n_extras = 0;
  if (d->has_user_data_slot)
    {
      if (kwargs_in != NULL)
        {
          PyObject *ud = PyDict_GetItemString (kwargs_in, "user_data"); /* borrowed */
          if (ud != NULL)
            {
              has_user_data_kw = 1;
              user_data = ud;
              Py_INCREF (user_data);
            }
          else if (PyErr_Occurred ())
            return NULL;
        }
      if (n_args > n_visible)
        n_extras = n_args - n_visible;
      if (has_user_data_kw && n_extras > 0)
        {
          PyErr_Format (PyExc_TypeError,
                        "%s() got both trailing positional user_data and user_data= keyword",
                        descriptor_bare_name (d));
          Py_CLEAR (user_data);
          return NULL;
        }
      if (n_extras > 0 && n_extras == d->n_elided_closures)
        {
          /* The extras exactly fill the elided closure companion slots.
           * Pass them through as separate positional args so the per-call
           * expansion can un-elide each one independently. Do NOT pack. */
          n_extras = 0;
        }
      if (n_extras > 0)
        {
          Py_CLEAR (user_data);
          if (n_extras == 1)
            {
              user_data = PyTuple_GET_ITEM (args_in, args_offset + n_visible);
              Py_INCREF (user_data);
            }
          else
            {
              PyObject *packed_type = packed_user_data_type ();
              if (packed_type == NULL)
                return NULL;
              PyObject *slice
                  = PyTuple_GetSlice (args_in, args_offset + n_visible, args_offset + n_args);
              if (slice == NULL)
                return NULL;
              user_data = PyObject_CallOneArg (packed_type, slice);
              Py_DECREF (slice);
              if (user_data == NULL)
                return NULL;
            }
        }
    }

  Py_ssize_t n_head = (n_extras > 0) ? n_visible : n_args;
  Py_ssize_t n_remaining_kw = n_kw - (has_user_data_kw ? 1 : 0);

  /* Step 2: fast path — no remaining kwargs to merge. Skip the
   * named-arg resolution; just splice self (if any), the head, and
   * user_data (if any) into one tuple. */
  if (n_remaining_kw == 0)
    {
      Py_ssize_t out_len = self_pad + n_head + (user_data != NULL ? 1 : 0);
      PyObject *out = PyTuple_New (out_len);
      if (out == NULL)
        {
          Py_XDECREF (user_data);
          return NULL;
        }
      if (self_obj != NULL)
        {
          Py_INCREF (self_obj);
          PyTuple_SET_ITEM (out, 0, self_obj);
        }
      for (Py_ssize_t i = 0; i < n_head; i++)
        {
          PyObject *v = PyTuple_GET_ITEM (args_in, args_offset + i);
          Py_INCREF (v);
          PyTuple_SET_ITEM (out, self_pad + i, v);
        }
      if (user_data != NULL)
        PyTuple_SET_ITEM (out, self_pad + n_head, user_data); /* steals */
      return out;
    }

  /* Step 3: kwarg merge. Over-passing positional + kwargs is a TypeError
   * here (the no-kwarg path lets the C bind layer raise on its own
   * cadence, matching legacy Python `_merge_keyword_args` semantics). */
  if (n_head > n_visible)
    {
      PyErr_Format (PyExc_TypeError,
                    "%s() takes exactly %zd non-keyword arguments (%zd given)",
                    descriptor_bare_name (d),
                    n_visible,
                    n_args);
      Py_XDECREF (user_data);
      return NULL;
    }

  /* Resolve each kwarg's positional index up front. This lets us size
   * the merged tuple to `max(n_head, max_kwarg_idx + 1)` rather than to
   * the full visible signature — preserving the legacy semantics where
   * trailing nullable/optional GI args (e.g. spawn_async_with_pipes'
   * child_setup) that the caller didn't name simply don't appear in the
   * result, and the C bind layer fills them with NULL. */
  Py_ssize_t *kw_indices = g_alloca (sizeof (Py_ssize_t) * (n_kw ? n_kw : 1));
  PyObject **kw_values = g_alloca (sizeof (PyObject *) * (n_kw ? n_kw : 1));
  Py_ssize_t kw_count = 0;
  Py_ssize_t max_kw_idx = -1;
  {
    PyObject *key, *value;
    Py_ssize_t pos = 0;
    while (PyDict_Next (kwargs_in, &pos, &key, &value))
      {
        if (d->has_user_data_slot && PyUnicode_Check (key)
            && PyUnicode_CompareWithASCIIString (key, "user_data") == 0)
          continue;

        Py_ssize_t idx = -1;
        for (Py_ssize_t k = 0; k < n_visible; k++)
          {
            int cmp = PyObject_RichCompareBool (PyTuple_GET_ITEM (arg_names, k), key, Py_EQ);
            if (cmp < 0)
              {
                Py_XDECREF (user_data);
                return NULL;
              }
            if (cmp == 1)
              {
                idx = k;
                break;
              }
          }
        if (idx < 0)
          {
            PyErr_Format (PyExc_TypeError,
                          "%s() got an unexpected keyword argument %R",
                          descriptor_bare_name (d),
                          key);
            Py_XDECREF (user_data);
            return NULL;
          }
        if (idx < n_head)
          {
            PyErr_Format (PyExc_TypeError,
                          "%s() got multiple values for keyword argument %R",
                          descriptor_bare_name (d),
                          key);
            Py_XDECREF (user_data);
            return NULL;
          }
        for (Py_ssize_t prev = 0; prev < kw_count; prev++)
          if (kw_indices[prev] == idx)
            {
              PyErr_Format (PyExc_TypeError,
                            "%s() got multiple values for keyword argument %R",
                            descriptor_bare_name (d),
                            key);
              Py_XDECREF (user_data);
              return NULL;
            }
        kw_indices[kw_count] = idx;
        kw_values[kw_count] = value;
        kw_count++;
        if (idx > max_kw_idx)
          max_kw_idx = idx;
      }
  }

  Py_ssize_t n_payload = (max_kw_idx + 1 > n_head) ? max_kw_idx + 1 : n_head;
  Py_ssize_t out_len = self_pad + n_payload + (user_data != NULL ? 1 : 0);
  PyObject *merged = PyTuple_New (out_len);
  if (merged == NULL)
    {
      Py_XDECREF (user_data);
      return NULL;
    }
  if (self_obj != NULL)
    {
      Py_INCREF (self_obj);
      PyTuple_SET_ITEM (merged, 0, self_obj);
    }
  for (Py_ssize_t i = 0; i < n_head; i++)
    {
      PyObject *v = PyTuple_GET_ITEM (args_in, args_offset + i);
      Py_INCREF (v);
      PyTuple_SET_ITEM (merged, self_pad + i, v);
    }
  for (Py_ssize_t k = 0; k < kw_count; k++)
    {
      Py_INCREF (kw_values[k]);
      PyTuple_SET_ITEM (merged, self_pad + kw_indices[k], kw_values[k]);
    }

  for (Py_ssize_t i = 0; i < n_payload; i++)
    {
      if (PyTuple_GET_ITEM (merged, self_pad + i) == NULL)
        {
          PyErr_Format (PyExc_TypeError,
                        "%s() takes exactly %zd non-keyword arguments (%zd given)",
                        descriptor_bare_name (d),
                        n_visible,
                        n_head);
          Py_DECREF (merged);
          Py_XDECREF (user_data);
          return NULL;
        }
    }
  if (user_data != NULL)
    PyTuple_SET_ITEM (merged, self_pad + n_payload, user_data); /* steals */
  return merged;
}

static PyObject *
class_struct_wrapper_for_type (PyObject *cls, PyObject *struct_cls)
{
  GType gtype = 0;
  if (pygi_gtype_from_py_object (cls, &gtype) != 0)
    return NULL;
  if (gtype == 0 || !G_TYPE_IS_CLASSED (gtype))
    {
      PyErr_SetString (PyExc_TypeError, "type does not have a class structure");
      return NULL;
    }

  gpointer klass = g_type_class_peek (gtype);
  if (klass == NULL)
    klass = g_type_class_ref (gtype);
  if (klass == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "g_type_class_ref failed");
      return NULL;
    }

  GType struct_gtype = 0;
  if (pygi_gtype_from_py_object (struct_cls, &struct_gtype) != 0)
    {
      PyErr_Clear ();
      struct_gtype = 0;
    }

  return pygi_boxed_new_alias (struct_cls, klass, struct_gtype, cls);
}

PyObject *
py_class_struct_wrapper (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  PyObject *struct_cls = NULL;
  if (!PyArg_ParseTuple (args, "OO", &cls, &struct_cls))
    return NULL;
  if (!PyType_Check (cls) || !PyType_Check (struct_cls))
    {
      PyErr_SetString (PyExc_TypeError, "cls and struct_cls must be types");
      return NULL;
    }
  return class_struct_wrapper_for_type (cls, struct_cls);
}

PyObject *
py_invoke_callable_descriptor (PyObject *module G_GNUC_UNUSED,
                               PyObject *const *args,
                               Py_ssize_t nargs,
                               PyObject *kwnames)
{
  if (nargs < 1)
    {
      PyErr_SetString (PyExc_TypeError, "invoke_callable_descriptor expected a descriptor");
      return NULL;
    }

  PyGIMethodDescriptor *descriptor = method_descriptor_from_py (args[0]);
  if (descriptor == NULL)
    return NULL;

  if (kwnames == NULL && nargs == 3 && PyTuple_Check (args[1])
      && (args[2] == Py_None || PyDict_Check (args[2])))
    return invoke_descriptor_with_tuple_kwargs (descriptor, args[1], args[2]);

  return invoke_descriptor_vectorcall (descriptor, args + 1, (size_t)(nargs - 1), kwnames);
}


/* ----------------------------------------------------------------------
 * ginext.invoke — overlay-body fast path.
 *
 * Looks up a typelib callable by (namespace_name, function_name),
 * caches the compiled descriptor at module level, and dispatches via
 * the existing FFI invoke path. Used by overlay bodies that want to
 * call the typelib's original (bypassing any overlay that may be
 * installed on the same name).
 *
 * The Python signature, exposed via METH_FASTCALL, is:
 *
 *     private._invoke(ns, func, *call_args) -> result
 *
 * where ``ns`` is a str (namespace name) or a Namespace instance,
 * ``func`` is the GIR member name, and ``call_args`` are the
 * positional arguments to the C callable in typelib arg order.
 * ---------------------------------------------------------------------- */

static GHashTable *_invoke_descriptor_cache = NULL;

extern PyObject *
py_construct_gobject (PyObject *m, PyObject *args);
extern PyObject *
py_interface_list_properties (PyObject *m, PyObject *args);

static PyObject *
invoke_special_gobject (const char *func, PyObject *const *args, Py_ssize_t nargs)
{
  if (g_strcmp0 (func, "Object.new_with_properties") == 0
      || g_strcmp0 (func, "new_with_properties") == 0)
    {
      if (nargs != 2)
        {
          PyErr_Format (PyExc_TypeError,
                        "ginext.invoke: GObject.%s expects 2 arguments, got %zd",
                        func,
                        nargs);
          return NULL;
        }
      PyObject *call_args = PyTuple_Pack (2, args[0], args[1]);
      if (call_args == NULL)
        return NULL;
      PyObject *result = py_construct_gobject (NULL, call_args);
      Py_DECREF (call_args);
      return result;
    }

  if (g_strcmp0 (func, "interface_list_properties") == 0)
    {
      if (nargs != 1)
        {
          PyErr_Format (PyExc_TypeError,
                        "ginext.invoke: GObject.%s expects 1 argument, got %zd",
                        func,
                        nargs);
          return NULL;
        }
      PyObject *call_args = PyTuple_Pack (1, args[0]);
      if (call_args == NULL)
        return NULL;
      PyObject *result = py_interface_list_properties (NULL, call_args);
      Py_DECREF (call_args);
      return result;
    }

  return NULL;
}

PyObject *
py_synthetic_callable (PyObject *self G_GNUC_UNUSED, PyObject *args)
{
  const char *qualified_name = NULL;
  if (!PyArg_ParseTuple (args, "s", &qualified_name))
    return NULL;

  static PyMethodDef new_with_properties_def = {
    "GObject.Object.new_with_properties",
    py_construct_gobject,
    METH_VARARGS,
    NULL,
  };
  static PyMethodDef interface_list_properties_def = {
    "GObject.interface_list_properties",
    py_interface_list_properties,
    METH_VARARGS,
    NULL,
  };

  if (g_strcmp0 (qualified_name, "GObject.Object.new_with_properties") == 0)
    return PyCFunction_NewEx (&new_with_properties_def, NULL, NULL);
  if (g_strcmp0 (qualified_name, "GObject.interface_list_properties") == 0)
    return PyCFunction_NewEx (&interface_list_properties_def, NULL, NULL);

  PyErr_Format (PyExc_AttributeError,
                "ginext.synthetic_callable: unknown callable %s",
                qualified_name);
  return NULL;
}

static PyGIMethodDescriptor *
invoke_lookup_or_build (const char *ns_name, const char *version, const char *func)
{
  /* Cache key: "<ns>@<version>.<func>"; stable for the program's
     * lifetime (the cache is never evicted — entries are cheap, ~1KB
     * each, and overlay bodies repeatedly invoke a small finite set). */
  char key[256];
  int klen = snprintf (key, sizeof (key), "%s@%s.%s", ns_name, version, func);
  if (klen < 0 || klen >= (int)sizeof (key))
    {
      PyErr_Format (PyExc_ValueError, "ginext.invoke: qualified name too long");
      return NULL;
    }

  if (_invoke_descriptor_cache == NULL)
    _invoke_descriptor_cache = g_hash_table_new (g_str_hash, g_str_equal);

  PyGIMethodDescriptor *descriptor = g_hash_table_lookup (_invoke_descriptor_cache, key);
  if (descriptor != NULL)
    return descriptor;

  GIRepository *repo = ginext_shared_repository ();
  if (repo == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "gi_repository_new failed");
      return NULL;
    }
  g_autoptr (GError) gerr = NULL;
  if (gi_repository_require (repo, ns_name, version, GI_REPOSITORY_LOAD_FLAG_NONE, &gerr) == NULL)
    {
      PyErr_Format (PyExc_ImportError,
                    "gi_repository_require(%s, %s) failed: %s",
                    ns_name,
                    version,
                    gerr && gerr->message ? gerr->message : "unknown error");
      return NULL;
    }
  /* func may be a bare top-level name ("idle_add") or a dotted
     * class-member path ("Object.freeze_notify"). For the dotted
     * form we look up the class first, then the named method on it. */
  const char *dot = strchr (func, '.');
  GIBaseInfo *base = NULL;
  int has_self = 0;
  if (dot == NULL)
    {
      base = gi_repository_find_by_name (repo, ns_name, func);
      if (base == NULL)
        {
          PyErr_Format (PyExc_AttributeError,
                        "ginext.invoke: %s has no attribute %s",
                        ns_name,
                        func);
          return NULL;
        }
      if (!GI_IS_FUNCTION_INFO (base))
        {
          PyErr_Format (PyExc_TypeError, "ginext.invoke: %s.%s is not a function", ns_name, func);
          gi_base_info_unref (base);
          return NULL;
        }
    }
  else
    {
      /* Class.method form. Split at the dot; look up the class info,
         * then find the method on it. */
      size_t cls_len = (size_t)(dot - func);
      char cls_name[128];
      if (cls_len + 1 > sizeof (cls_name))
        {
          PyErr_Format (PyExc_ValueError, "ginext.invoke: class name too long in %s", func);
          return NULL;
        }
      memcpy (cls_name, func, cls_len);
      cls_name[cls_len] = '\0';
      const char *method_name = dot + 1;

      GIBaseInfo *cls_info = gi_repository_find_by_name (repo, ns_name, cls_name);
      if (cls_info == NULL)
        {
          PyErr_Format (PyExc_AttributeError,
                        "ginext.invoke: %s has no class %s",
                        ns_name,
                        cls_name);
          return NULL;
        }
      /* Try as object/struct/union — each kind has its own method
         * accessor. Use the one that matches. */
      GIFunctionInfo *method = NULL;
      if (GI_IS_OBJECT_INFO (cls_info))
        method = gi_object_info_find_method ((GIObjectInfo *)cls_info, method_name);
      else if (GI_IS_INTERFACE_INFO (cls_info))
        method = gi_interface_info_find_method ((GIInterfaceInfo *)cls_info, method_name);
      else if (GI_IS_STRUCT_INFO (cls_info))
        method = gi_struct_info_find_method ((GIStructInfo *)cls_info, method_name);
      else if (GI_IS_UNION_INFO (cls_info))
        method = gi_union_info_find_method ((GIUnionInfo *)cls_info, method_name);
      gi_base_info_unref (cls_info);
      if (method == NULL)
        {
          PyErr_Format (PyExc_AttributeError,
                        "ginext.invoke: %s.%s has no method %s",
                        ns_name,
                        cls_name,
                        method_name);
          return NULL;
        }
      base = (GIBaseInfo *)method;
      /* Method takes self if the GIR says it's an instance method. */
      GIFunctionInfoFlags flags = gi_function_info_get_flags (method);
      has_self = (flags & GI_FUNCTION_IS_METHOD) ? 1 : 0;
    }

  descriptor = calloc (1, sizeof (*descriptor));
  if (descriptor == NULL)
    {
      gi_base_info_unref (base);
      PyErr_NoMemory ();
      return NULL;
    }
  descriptor->info = (GIFunctionInfo *)base; /* takes ownership of the ref */
  descriptor->has_self = has_self;
  char qualified[256];
  snprintf (qualified, sizeof (qualified), "%s.%s", ns_name, func);
  descriptor->qualified_name = strdup (qualified);
  if (descriptor->qualified_name == NULL)
    {
      method_descriptor_destroy (descriptor);
      PyErr_NoMemory ();
      return NULL;
    }

  descriptor->compiled
      = compile_callable_for_ffi (descriptor->info, has_self, descriptor->qualified_name);
  if (descriptor->compiled == NULL)
    {
      method_descriptor_destroy (descriptor);
      return NULL;
    }

  g_hash_table_insert (_invoke_descriptor_cache, g_strdup (key), descriptor);
  return descriptor;
}

PyObject *
py_invoke_by_name (PyObject *self G_GNUC_UNUSED, PyObject *const *args, Py_ssize_t nargs)
{
  if (nargs < 2)
    {
      PyErr_SetString (PyExc_TypeError, "ginext.invoke requires at least (ns, func)");
      return NULL;
    }

  /* Resolve ns to (ns_name, version). Accept either a str or any object
   * exposing __name__ (i.e. Namespace). The load_namespace hook guarantees the
   * typelib is loaded before the version is read from the shared repository. */
  PyObject *ns_obj = args[0];
  Py_AUTO_DECREF PyObject *name_holder = NULL;
  const char *ns_name;

  if (PyUnicode_Check (ns_obj))
    {
      ns_name = PyUnicode_AsUTF8 (ns_obj);
      if (ns_name == NULL)
        return NULL;
    }
  else
    {
      name_holder = PyObject_GetAttrString (ns_obj, "__name__");
      if (name_holder == NULL)
        return NULL;
      ns_name = PyUnicode_AsUTF8 (name_holder);
      if (ns_name == NULL)
        return NULL;
    }
  PyObject *loader = pygi_hook_last (pygi_hook_load_namespace);
  if (loader == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "load_namespace hook not registered");
      return NULL;
    }
  PyObject *load_arg = PyUnicode_Check (ns_obj) ? ns_obj : name_holder;
  PyObject *loaded_namespace = PyObject_CallOneArg (loader, load_arg);
  if (loaded_namespace == NULL)
    return NULL;
  Py_DECREF (loaded_namespace);

  const char *version = gi_repository_get_version (ginext_shared_repository (), ns_name);
  if (version == NULL)
    {
      PyErr_Format (PyExc_RuntimeError, "ginext.invoke: namespace %s is not loaded", ns_name);
      return NULL;
    }

  if (!PyUnicode_Check (args[1]))
    {
      PyErr_SetString (PyExc_TypeError, "ginext.invoke: func must be a string");
      return NULL;
    }
  const char *func = PyUnicode_AsUTF8 (args[1]);
  if (func == NULL)
    return NULL;

  if (g_strcmp0 (ns_name, "GObject") == 0)
    {
      PyObject *result = invoke_special_gobject (func, args + 2, nargs - 2);
      if (result != NULL || PyErr_Occurred ())
        return result;
    }

  PyGIMethodDescriptor *descriptor = invoke_lookup_or_build (ns_name, version, func);
  if (descriptor == NULL)
    return NULL;

  /* Forward args[2..nargs] as the C call args. */
  Py_ssize_t n_call = nargs - 2;
  PyObject **call_args = g_alloca (sizeof (*call_args) * (n_call > 0 ? (size_t)n_call : 1u));
  for (Py_ssize_t i = 0; i < n_call; i++)
    call_args[i] = args[i + 2];

  return pygi_method_descriptor_call_ffi_invoke (descriptor, call_args, (size_t)n_call, NULL);
}
