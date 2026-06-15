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
#include "GObject/Boxed.h"
#include "GObject/Closure.h"
#include "GObject/Object.h"
#include "GObject/Object-info.h"
#include "marshal/enum.h"
#include "GIRepository/BaseInfo.h"
#include "GIRepository/Info.h"
#include "marshal/gvalue.h"
#include "marshal/marshal.h"
#include "marshal/scalar.h"
#include "marshal/string.h"
#include "invoke/ffi/invoke.h"
#include "runtime/type-info.h"
#include "runtime/class-registry.h"
#include "runtime/module_funcs.h"
#include "gimeta-helpers.h"
#include "common.h"

#include <ffi.h>
#include <girepository/girepository.h>
#include <stdint.h>
#include <string.h>

typedef struct
{
  GIArgInfo *arg_info;
  GITypeInfo *type_info;
  GITypeInfo *array_elem_info;
  GITypeTag tag;
  GITypeTag array_elem_tag;
  GIDirection direction;
  GITransfer transfer;
  ffi_type *ffi_type;
  int array_length_arg;
  int length_owner_array;
  gboolean is_closure;
  GType wrapper_gtype;
} PyGICallbackArgPlan;

typedef struct
{
  PyObject *callable;
  PyObject *py_user_data;
  PyObject *namespace;
  GICallableInfo *callback_info;
  GITypeInfo *return_type;
  GITypeTag return_tag;
  GITransfer return_transfer;
  int n_args;
  int n_out_args;
  /* Positional arity of the Python callable, cached at closure
   * creation. -1 means uninspectable or accepts *args — trampoline
   * passes the full arg list. Otherwise the trampoline trims to this
   * length so a `def cb(): ...` against a C-side signature with
   * `user_data` doesn't surface "got 1 arg, expected 0". */
  int callable_arity;
  PyGICallbackArgPlan *args;
  ffi_type **ffi_arg_types;
  ffi_type *ffi_return_type;
  ffi_cif cif;
  ffi_closure *closure;
  void *code;
  GIScopeType scope;
  gboolean include_array_length_args;
  /* For transfer-nothing utf8/filename callback returns: we strdup the
   * Python str into pinned_return and free it on the next call or on
   * closure teardown, since the caller won't free it. */
  char *pinned_return;
} PyGICallbackClosure;

typedef struct
{
  PyObject_HEAD PyGICompiledCallable *compiled;
  GICallableInfo *callback_info;
  PyObject *namespace;
  char *qualified_name;
  Py_ssize_t user_data_py_index;
  gpointer user_data_ptr;
} PyGIReverseCallback;

static GMutex callback_deferred_free_lock;
static GList *callback_deferred_free_list = NULL;
PyTypeObject *ginext_reverse_callback_type = NULL;

static void
callback_closure_free (PyGICallbackClosure *closure);

static void
callback_closure_release_py_refs (PyGICallbackClosure *closure)
{
  if (closure == NULL)
    return;
  Py_CLEAR (closure->callable);
  Py_CLEAR (closure->py_user_data);
  Py_CLEAR (closure->namespace);
}

static void
reverse_callback_dealloc (PyObject *self)
{
  PyGIReverseCallback *callback = (PyGIReverseCallback *)self;
  pygi_compiled_callable_destroy_for_ffi (callback->compiled);
  g_clear_pointer (&callback->callback_info, gi_base_info_unref);
  Py_CLEAR (callback->namespace);
  free (callback->qualified_name);
  Py_TYPE (self)->tp_free (self);
}

static PyObject *
reverse_callback_repr (PyObject *self)
{
  PyGIReverseCallback *callback = (PyGIReverseCallback *)self;
  return PyUnicode_FromFormat ("<callback '%s'>",
                               callback->qualified_name != NULL ? callback->qualified_name : "?");
}

static PyObject *
reverse_callback_call (PyObject *self, PyObject *args, PyObject *kw)
{
  PyGIReverseCallback *callback = (PyGIReverseCallback *)self;
  if (kw != NULL && PyDict_GET_SIZE (kw) != 0)
    {
      PyErr_SetString (PyExc_TypeError, "callback wrappers do not accept keyword arguments");
      return NULL;
    }

  Py_ssize_t nargs = PyTuple_GET_SIZE (args);
  Py_ssize_t full_nargs = nargs + (callback->user_data_py_index >= 0 ? 1 : 0);
  PyObject **argv = g_new0 (PyObject *, (gsize)(full_nargs > 0 ? full_nargs : 1));
  if (argv == NULL)
    return PyErr_NoMemory ();

  if (callback->user_data_py_index >= 0)
    {
      PyObject *user_data = callback->user_data_ptr != NULL
                                ? PyLong_FromVoidPtr (callback->user_data_ptr)
                                : Py_NewRef (Py_None);
      if (user_data == NULL)
        {
          g_free (argv);
          return NULL;
        }

      Py_ssize_t src = 0;
      for (Py_ssize_t dst = 0; dst < full_nargs; dst++)
        {
          if (dst == callback->user_data_py_index)
            argv[dst] = user_data;
          else
            argv[dst] = PyTuple_GET_ITEM (args, src++);
        }
    }
  else
    {
      for (Py_ssize_t i = 0; i < nargs; i++)
        argv[i] = PyTuple_GET_ITEM (args, i);
    }

  PyGICallableDescriptor descriptor = {
    .compiled = callback->compiled,
    .info = (GIFunctionInfo *)callback->callback_info,
    .has_self = 0,
    .qualified_name = callback->qualified_name,
    .namespace = callback->namespace,
  };
  PyObject *result
      = pygi_callable_descriptor_call_ffi_invoke (&descriptor, argv, (size_t)full_nargs, NULL);
  if (callback->user_data_py_index >= 0)
    Py_DECREF (argv[callback->user_data_py_index]);
  g_free (argv);
  return result;
}

static ffi_type *
callback_ffi_type_for_tag (GITypeTag tag, GITypeInfo *ti, gboolean pointer)
{
  if (pointer)
    return &ffi_type_pointer;
  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (ti);
      if (iface != NULL && (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)))
        {
          GITypeTag storage = gi_enum_info_get_storage_type ((GIEnumInfo *)iface);
          return callback_ffi_type_for_tag (storage, ti, FALSE);
        }
      return &ffi_type_pointer;
    }
  switch (tag)
    {
    case GI_TYPE_TAG_VOID:
      return &ffi_type_void;
    case GI_TYPE_TAG_BOOLEAN:
      return &ffi_type_sint32;
    case GI_TYPE_TAG_INT8:
      return &ffi_type_sint8;
    case GI_TYPE_TAG_UINT8:
      return &ffi_type_uint8;
    case GI_TYPE_TAG_INT16:
      return &ffi_type_sint16;
    case GI_TYPE_TAG_UINT16:
      return &ffi_type_uint16;
    case GI_TYPE_TAG_INT32:
      return &ffi_type_sint32;
    case GI_TYPE_TAG_UINT32:
    case GI_TYPE_TAG_UNICHAR:
      return &ffi_type_uint32;
    case GI_TYPE_TAG_INT64:
      return &ffi_type_sint64;
    case GI_TYPE_TAG_UINT64:
    case GI_TYPE_TAG_GTYPE:
      return &ffi_type_uint64;
    case GI_TYPE_TAG_FLOAT:
      return &ffi_type_float;
    case GI_TYPE_TAG_DOUBLE:
      return &ffi_type_double;
    default:
      return &ffi_type_pointer;
    }
}

static gboolean
callable_info_find_user_data_arg (GICallableInfo *callback_info, Py_ssize_t *out_py_index)
{
  int n_args = (int)gi_callable_info_get_n_args (callback_info);
  Py_ssize_t py_index = 0;
  for (int i = 0; i < n_args; i++)
    {
      g_autoptr (GIArgInfo) arg_info = gi_callable_info_get_arg (callback_info, (guint)i);
      if (arg_info == NULL || gi_arg_info_get_direction (arg_info) == GI_DIRECTION_OUT)
        continue;

      g_autoptr (GITypeInfo) type_info = gi_arg_info_get_type_info (arg_info);
      const char *name = gi_base_info_get_name ((GIBaseInfo *)arg_info);
      if (type_info != NULL && gi_type_info_get_tag (type_info) == GI_TYPE_TAG_VOID
          && gi_type_info_is_pointer (type_info) && name != NULL
          && (strcmp (name, "user_data") == 0 || strcmp (name, "data") == 0))
        {
          *out_py_index = py_index;
          return TRUE;
        }
      py_index++;
    }
  return FALSE;
}

static PyObject *
reverse_callback_new (PyObject *namespace,
                      GICallableInfo *callback_info,
                      gpointer callback_ptr,
                      gpointer user_data_ptr)
{
  if (ginext_reverse_callback_type == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "reverse callback type not initialized");
      return NULL;
    }

  const char *namespace_name = gi_base_info_get_namespace ((GIBaseInfo *)callback_info);
  const char *name = gi_base_info_get_name ((GIBaseInfo *)callback_info);
  g_autofree char *qualified_name = g_strdup_printf ("%s.%s",
                                                     namespace_name != NULL ? namespace_name : "?",
                                                     name != NULL ? name : "callback");
  PyGICompiledCallable *compiled
      = pygi_compile_callable_for_ffi_target (callback_info, callback_ptr, 0, qualified_name);
  if (compiled == NULL)
    return NULL;

  PyObject *obj = PyType_GenericAlloc (ginext_reverse_callback_type, 0);
  if (obj == NULL)
    {
      pygi_compiled_callable_destroy_for_ffi (compiled);
      return NULL;
    }

  PyGIReverseCallback *callback = (PyGIReverseCallback *)obj;
  callback->compiled = compiled;
  callback->callback_info = (GICallableInfo *)gi_base_info_ref ((GIBaseInfo *)callback_info);
  callback->namespace = Py_NewRef (namespace);
  callback->qualified_name = g_strdup (qualified_name);
  callback->user_data_ptr = user_data_ptr;
  callback->user_data_py_index = -1;
  if (callback->qualified_name == NULL)
    {
      Py_DECREF (obj);
      return PyErr_NoMemory ();
    }
  if (!callable_info_find_user_data_arg (callback_info, &callback->user_data_py_index))
    callback->user_data_py_index = -1;
  return obj;
}

/* Returns the positional-arg count of a Python callable, or -1 for
 * *args / uninspectable. Mirrors signal.py:_callback_arity. */
static int
callback_inspect_arity (PyObject *callable)
{
  PyObject *func = callable;
  int is_bound = 0;

  /* Unwrap bound method — self counts as one positional arg. */
  if (PyMethod_Check (callable))
    {
      func = PyMethod_GET_FUNCTION (callable);
      is_bound = 1;
    }

  if (!PyFunction_Check (func))
    {
      /* Try __wrapped__ for decorated functions. */
      Py_AUTO_DECREF PyObject *wrapped = PyObject_GetAttrString (func, "__wrapped__");
      if (wrapped != NULL)
        return callback_inspect_arity (wrapped);
      PyErr_Clear ();
      return -1;
    }

  PyCodeObject *code = (PyCodeObject *)PyFunction_GET_CODE (func); /* borrowed */
  long argcount = code->co_argcount;
  long flags = code->co_flags;

  /* CO_VARARGS = 0x04 — callable accepts *args, arity is unlimited. */
  if (flags & 0x04)
    return -1;

  return (int)(argcount - is_bound);
}
static PyObject *
callback_bound_arg_gtypes_obj (PyObject *callable)
{
  PyObject *bound = PyObject_GetAttrString (callable, "ginext_bound_callback_gtypes");
  if (bound != NULL)
    return bound;
  PyErr_Clear ();
  Py_AUTO_DECREF PyObject *func = PyObject_GetAttrString (callable, "__func__");
  if (func == NULL)
    {
      PyErr_Clear ();
      return NULL;
    }
  bound = PyObject_GetAttrString (func, "ginext_bound_callback_gtypes");
  if (bound == NULL)
    PyErr_Clear ();
  return bound;
}

static int
callback_apply_bound_arg_gtypes (PyGICallbackClosure *closure)
{
  Py_AUTO_DECREF PyObject *bound = callback_bound_arg_gtypes_obj (closure->callable);
  if (bound == NULL)
    return 0;
  if (!PyTuple_Check (bound))
    return 0;
  Py_ssize_t n = PyTuple_GET_SIZE (bound);
  Py_ssize_t limit = n < closure->n_args ? n : closure->n_args;
  for (Py_ssize_t i = 0; i < limit; i++)
    {
      unsigned long long raw = PyLong_AsUnsignedLongLong (PyTuple_GET_ITEM (bound, i));
      if (PyErr_Occurred ())
        return -1;
      closure->args[i].wrapper_gtype = (GType)raw;
    }
  return 0;
}

static gboolean
callback_arg_is_void_pointer (GIArgInfo *arg_info)
{
  g_autoptr (GITypeInfo) type_info = gi_arg_info_get_type_info (arg_info);
  return type_info != NULL && gi_type_info_get_tag (type_info) == GI_TYPE_TAG_VOID
         && gi_type_info_is_pointer (type_info);
}

static gboolean
callback_arg_is_closure (GICallableInfo *callback_info, int arg_index, GIArgInfo *arg_info)
{
  unsigned int closure_index = 0;
  if (gi_arg_info_get_closure_index (arg_info, &closure_index) && (int)closure_index == arg_index)
    return TRUE;

  const char *name = gi_base_info_get_name ((GIBaseInfo *)arg_info);
  if (name == NULL)
    return FALSE;
  if (arg_index != (int)gi_callable_info_get_n_args (callback_info) - 1)
    return FALSE;
  if (!callback_arg_is_void_pointer (arg_info))
    return FALSE;
  return strcmp (name, "user_data") == 0 || strcmp (name, "data") == 0;
}

static gboolean
callback_arg_is_trailing_user_data (PyGICallbackClosure *closure, int arg_index)
{
  if (closure == NULL || arg_index != closure->n_args - 1)
    return FALSE;
  PyGICallbackArgPlan *arg = &closure->args[arg_index];
  if (arg->direction != GI_DIRECTION_IN)
    return FALSE;
  if (arg->tag != GI_TYPE_TAG_VOID || !gi_type_info_is_pointer (arg->type_info))
    return FALSE;
  const char *name = gi_base_info_get_name ((GIBaseInfo *)arg->arg_info);
  if (name == NULL)
    return FALSE;
  return strcmp (name, "user_data") == 0 || strcmp (name, "data") == 0;
}

static PyGICallbackClosure *
callback_closure_alloc (PyObject *callable, GICallableInfo *callback_info)
{
  PyGICallbackClosure *closure = g_new0 (PyGICallbackClosure, 1);
  Py_INCREF (callable);
  closure->callable = callable;
  PyObject *namespace = pygi_namespace_context ();
  if (namespace == NULL)
    {
      callback_closure_release_py_refs (closure);
      g_free (closure);
      return NULL;
    }
  closure->namespace = Py_NewRef (namespace);
  closure->callable_arity = callback_inspect_arity (callable);
  closure->callback_info = (GICallableInfo *)gi_base_info_ref ((GIBaseInfo *)callback_info);
  closure->return_type = gi_callable_info_get_return_type (callback_info);
  closure->return_tag = gi_type_info_get_tag (closure->return_type);
  closure->return_transfer = gi_callable_info_get_caller_owns (callback_info);
  closure->ffi_return_type = callback_ffi_type_for_tag (
      closure->return_tag, closure->return_type,
      gi_type_info_is_pointer (closure->return_type));
  closure->n_args = (int)gi_callable_info_get_n_args (callback_info);
  closure->args = g_new0 (PyGICallbackArgPlan, (gsize)(closure->n_args > 0 ? closure->n_args : 1));
  closure->ffi_arg_types = g_new0 (ffi_type *, (gsize)(closure->n_args > 0 ? closure->n_args : 1));
  for (int i = 0; i < closure->n_args; i++)
    {
      closure->args[i].array_length_arg = -1;
      closure->args[i].length_owner_array = -1;
    }
  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      arg->arg_info = gi_callable_info_get_arg (callback_info, (guint)i);
      arg->type_info = gi_arg_info_get_type_info (arg->arg_info);
      arg->tag = gi_type_info_get_tag (arg->type_info);
      arg->direction = gi_arg_info_get_direction (arg->arg_info);
      arg->transfer = gi_arg_info_get_ownership_transfer (arg->arg_info);
      arg->is_closure = arg->direction == GI_DIRECTION_IN
                        && callback_arg_is_closure (callback_info, i, arg->arg_info);
      arg->ffi_type = callback_ffi_type_for_tag (
          arg->tag, arg->type_info,
          arg->direction != GI_DIRECTION_IN || gi_type_info_is_pointer (arg->type_info));
      closure->ffi_arg_types[i] = arg->ffi_type;
      if (arg->tag == GI_TYPE_TAG_ARRAY
          && gi_type_info_get_array_type (arg->type_info) == GI_ARRAY_TYPE_C)
        {
          arg->array_elem_info = gi_type_info_get_param_type (arg->type_info, 0);
          arg->array_elem_tag = arg->array_elem_info != NULL
                                    ? gi_type_info_get_tag (arg->array_elem_info)
                                    : GI_TYPE_TAG_VOID;
          unsigned int len_idx = 0;
          if (gi_type_info_get_array_length_index (arg->type_info, &len_idx)
              && len_idx < (unsigned int)closure->n_args)
            {
              arg->array_length_arg = (int)len_idx;
              closure->args[len_idx].length_owner_array = i;
            }
        }
    }
  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      if (arg->direction != GI_DIRECTION_IN && arg->length_owner_array < 0)
        closure->n_out_args++;
    }
  if (callback_apply_bound_arg_gtypes (closure) != 0)
    {
      callback_closure_free (closure);
      return NULL;
    }
  return closure;
}

static void
callback_closure_free (PyGICallbackClosure *closure)
{
  if (closure == NULL)
    return;
  if (closure->closure != NULL)
    {
      ffi_closure_free (closure->closure);
      closure->closure = NULL;
    }
  /* Py_CLEAR (not Py_XDECREF) so a re-entrant call from the dealloc
   * path doesn't dereference the same field twice. The destroy_notify
   * route (pygi_callback_closure_destroy) can fire from inside the
   * trampoline's own teardown when a notified-scope source drops its
   * last ref while the dispatch is still unwinding. */
  Py_CLEAR (closure->callable);
  Py_CLEAR (closure->py_user_data);
  if (closure->args != NULL)
    {
      for (int i = 0; i < closure->n_args; i++)
        {
          g_clear_pointer (&closure->args[i].arg_info, gi_base_info_unref);
          g_clear_pointer (&closure->args[i].type_info, gi_base_info_unref);
          g_clear_pointer (&closure->args[i].array_elem_info, gi_base_info_unref);
        }
    }
  g_free (closure->args);
  g_free (closure->ffi_arg_types);
  g_clear_pointer (&closure->return_type, gi_base_info_unref);
  g_clear_pointer (&closure->callback_info, gi_base_info_unref);
  g_clear_pointer (&closure->pinned_return, g_free);
  g_free (closure);
}

static void
callback_closure_enqueue_deferred_free (PyGICallbackClosure *closure)
{
  /* scope=async callbacks are one-shot. The trampoline drops Python refs
   * before returning, but defers ffi_closure_free because we are still
   * executing from the closure's code page at this point. The next callback
   * allocation, or module teardown, drains this freelist. */
  g_mutex_lock (&callback_deferred_free_lock);
  callback_deferred_free_list = g_list_prepend (callback_deferred_free_list, closure);
  g_mutex_unlock (&callback_deferred_free_lock);
}

void
pygi_callback_closure_drain_deferred_frees (void)
{
  g_mutex_lock (&callback_deferred_free_lock);
  GList *closures = callback_deferred_free_list;
  callback_deferred_free_list = NULL;
  g_mutex_unlock (&callback_deferred_free_lock);

  for (GList *l = closures; l != NULL; l = l->next)
    callback_closure_free ((PyGICallbackClosure *)l->data);
  g_list_free (closures);
}

/**
 * callback_write_direct_value:
 * @value: Python value returned by the callback
 * @type_info: GI metadata for the return or out parameter, or %NULL
 * @tag: fallback GI tag when @type_info is unavailable
 * @transfer: ownership transfer for the callback slot
 * @dst: raw callback return or out-parameter storage
 *
 * Marshals callback scalar/direct-storage values into @dst using the
 * shared memory-target marshaller. Callback-specific pointer/object cases
 * are handled by callback_write_value() before this fallback is reached.
 */
static int
callback_write_direct_value (PyObject *value,
                             GITypeInfo *type_info,
                             GITypeTag tag,
                             GITransfer transfer,
                             void *dst)
{
  if (dst == NULL)
    return 0;
  if (tag == GI_TYPE_TAG_VOID)
    return 0;

  PyGIType type = { 0 };
  if (type_info != NULL)
    {
      if (pygi_type_from_gi (type_info, &type) != 0)
        return 0;
    }
  else if (pygi_type_from_gi_tag (tag, tag == GI_TYPE_TAG_VOID, &type) != 0)
    return 0;

  if (!pygi_type_is_direct_storage (&type))
    return 0;

  return pygi_marshal_from_py (value,
                               &(PyGIMarshalSlot){
                                   .type = type_info,
                                   .pygi_type = &type,
                                   .transfer = transfer,
                                   .transfer_set = true,
                                   .kind = PYGI_MARSHAL_TARGET_MEMORY,
                                   .target.memory = dst,
                               });
}

/**
 * callback_write_default_value:
 * @type_info: GI metadata for the callback return slot, or %NULL
 * @tag: fallback GI tag when @type_info is unavailable
 * @dst: raw callback return storage to initialize
 *
 * Writes the C-level default value used when a Python callback raises.
 * Direct-storage slots are zeroed by resolved storage size; pointer-like
 * unsupported slots fall back to %NULL.
 */
static void
callback_write_default_value (GITypeInfo *type_info, GITypeTag tag, void *dst)
{
  if (dst == NULL)
    return;
  if (tag == GI_TYPE_TAG_VOID)
    return;

  PyGIType type = { 0 };
  if (type_info != NULL && pygi_type_from_gi (type_info, &type) == 0)
    {
      gsize size = pygi_type_storage_size (&type);
      if (size != 0)
        {
          memset (dst, 0, size);
          return;
        }
    }

  if (type_info == NULL && pygi_type_from_gi_tag (tag, tag == GI_TYPE_TAG_VOID, &type) == 0)
    {
      gsize size = pygi_type_storage_size (&type);
      if (size != 0)
        {
          memset (dst, 0, size);
          return;
        }
    }

  *(gpointer *)dst = NULL;
}

static int
callback_write_value (PyObject *value,
                      GITypeInfo *type_info,
                      GITypeTag tag,
                      GITransfer transfer,
                      void *dst)
{
  if (tag == GI_TYPE_TAG_UTF8 || tag == GI_TYPE_TAG_FILENAME)
    {
      if (value == Py_None)
        {
          *(gpointer *)dst = NULL;
          return 0;
        }
      const char *s = NULL;
      Py_AUTO_DECREF PyObject *bytes = NULL;
      if (PyUnicode_Check (value))
        s = PyUnicode_AsUTF8 (value);
      else
        {
          bytes = PyBytes_FromObject (value);
          if (bytes != NULL)
            s = PyBytes_AsString (bytes);
        }
      if (s == NULL)
        return -1;
      *(gpointer *)dst = g_strdup (s);
      return 0;
    }

  if (tag == GI_TYPE_TAG_VOID)
    {
      /* Opaque OUT slot: write the Python int as a raw pointer value,
       * or NULL for None. The closure (or caller) is responsible for
       * interpreting it. */
      if (value == Py_None)
        {
          *(gpointer *)dst = NULL;
          return 0;
        }
      if (PyLong_Check (value))
        {
          *(gpointer *)dst = PyLong_AsVoidPtr (value);
          return PyErr_Occurred () ? -1 : 0;
        }
      *(gpointer *)dst = NULL;
      return 0;
    }
  if (tag == GI_TYPE_TAG_INTERFACE)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (type_info);
      if (iface != NULL && gi_base_info_is_named (iface, "GObject", "Closure"))
        {
          if (value == Py_None)
            {
              *(gpointer *)dst = NULL;
              return 0;
            }
          if (!PyCallable_Check (value))
            {
              PyErr_SetString (PyExc_TypeError, "GClosure return must be callable or None");
              return -1;
            }
          *(gpointer *)dst = pygi_closure_new (value);
          return *(gpointer *)dst != NULL ? 0 : -1;
        }
      if (iface != NULL && GI_IS_CALLBACK_INFO (iface))
        {
          /* OUT callback slot (e.g. DestroyNotify*): only None → NULL
           * is supported; arbitrary Python callables would require a
           * new ffi closure with no place to keep it alive. */
          *(gpointer *)dst = NULL;
          return 0;
        }
      if (iface != NULL && (GI_IS_OBJECT_INFO (iface) || GI_IS_INTERFACE_INFO (iface)))
        {
          if (value == Py_None)
            {
              *(gpointer *)dst = NULL;
              return 0;
            }
          GObject *object = pygi_gobject_get (value);
          if (object == NULL)
            return -1;
          /* Refcount accounting for vfunc/callback object returns:
           *   transfer-full: callee consumes a ref — always bump.
           *   transfer-none + wrapper has other Python holders: wrapper
           *     stays alive past the trampoline, so its GObject ref is
           *     enough; no bump (pygobject test_..._with_held_object
           *     asserts grefcount == 1).
           *   transfer-none + wrapper is our only ref: trampoline's
           *     final Py_DECREF will free the wrapper, which unrefs
           *     the GObject. Bump now so the C caller doesn't deref a
           *     freed pointer. Pygobject warns about the leak; we
           *     don't yet. */
          if (G_IS_OBJECT (object))
            {
              if (transfer == GI_TRANSFER_EVERYTHING || Py_REFCNT (value) <= 1)
                g_object_ref (object);
            }
          *(gpointer *)dst = object;
          return 0;
        }
      if (iface != NULL && (GI_IS_ENUM_INFO (iface) || GI_IS_FLAGS_INFO (iface)))
        {
          long long v = PyLong_AsLongLong (value);
          if (v == -1 && PyErr_Occurred ())
            return -1;
          *(int *)dst = (int)v;
          return 0;
        }
      if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
        {
          if (value == Py_None)
            {
              *(gpointer *)dst = NULL;
              return 0;
            }
          gpointer ptr = NULL;
          if (pygi_boxed_get (value, &ptr) != 0)
            return -1;
          *(gpointer *)dst = ptr;
          return 0;
        }
    }
  return callback_write_direct_value (value, type_info, tag, transfer, dst);
}

static PyObject *
callback_result_item (PyObject *result, int index, int total)
{
  if (total == 1)
    return result;
  if (PyTuple_Check (result) && PyTuple_GET_SIZE (result) == total)
    return PyTuple_GET_ITEM (result, index);
  return Py_None;
}

static int
callback_visible_arg_count (PyGICallbackClosure *closure, gboolean include_array_lengths)
{
  int count = 0;
  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      if (arg->direction == GI_DIRECTION_OUT)
        continue;
      if (arg->length_owner_array >= 0 && !include_array_lengths)
        continue;
      count++;
    }
  return count;
}

static int
callback_length_from_arg (void **args, PyGICallbackArgPlan *length_arg, int index)
{
  if (length_arg->direction == GI_DIRECTION_IN)
    {
      if (length_arg->tag == GI_TYPE_TAG_UINT64 || length_arg->tag == GI_TYPE_TAG_GTYPE)
        return (int)*(uint64_t *)args[index];
      if (length_arg->tag == GI_TYPE_TAG_INT64)
        return (int)*(int64_t *)args[index];
      if (length_arg->tag == GI_TYPE_TAG_UINT32)
        return (int)*(uint32_t *)args[index];
      return (int)*(int32_t *)args[index];
    }
  void *slot = *(void **)args[index];
  if (slot == NULL)
    return 0;
  if (length_arg->tag == GI_TYPE_TAG_UINT64 || length_arg->tag == GI_TYPE_TAG_GTYPE)
    return (int)*(uint64_t *)slot;
  if (length_arg->tag == GI_TYPE_TAG_INT64)
    return (int)*(int64_t *)slot;
  if (length_arg->tag == GI_TYPE_TAG_UINT32)
    return (int)*(uint32_t *)slot;
  return (int)*(int32_t *)slot;
}

static void
callback_set_length_arg (void **args, PyGICallbackArgPlan *length_arg, int index, int length)
{
  void *slot = length_arg->direction == GI_DIRECTION_IN ? args[index] : *(void **)args[index];
  if (slot == NULL)
    return;
  if (length_arg->tag == GI_TYPE_TAG_UINT64 || length_arg->tag == GI_TYPE_TAG_GTYPE)
    *(uint64_t *)slot = (uint64_t)length;
  else if (length_arg->tag == GI_TYPE_TAG_INT64)
    *(int64_t *)slot = (int64_t)length;
  else if (length_arg->tag == GI_TYPE_TAG_UINT32)
    *(uint32_t *)slot = (uint32_t)length;
  else
    *(int32_t *)slot = (int32_t)length;
}

static PyObject *
callback_array_to_py (PyGICallbackClosure *closure,
                      PyGICallbackArgPlan *arg,
                      void **args,
                      int index)
{
  void *base
      = arg->direction == GI_DIRECTION_IN ? *(void **)args[index] : *(void **)*(void **)args[index];
  if (arg->array_length_arg < 0)
    {
      if (gi_type_info_is_zero_terminated (arg->type_info)
          && (arg->array_elem_tag == GI_TYPE_TAG_UTF8
              || arg->array_elem_tag == GI_TYPE_TAG_FILENAME))
        return pygi_strv_to_py_list ((gchar **)base, GI_TRANSFER_NOTHING);
      return NULL;
    }

  PyGICallbackArgPlan *length_arg = &closure->args[arg->array_length_arg];
  int length = callback_length_from_arg (args, length_arg, arg->array_length_arg);
  if (length < 0)
    length = 0;
  PyObject *list = PyList_New ((Py_ssize_t)length);
  if (list == NULL)
    return NULL;
  if (base == NULL)
    return list;
  for (int i = 0; i < length; i++)
    {
      PyObject *item = NULL;
      if (arg->array_elem_tag == GI_TYPE_TAG_INT32)
        item = PyLong_FromLong (((int32_t *)base)[i]);
      else if (arg->array_elem_tag == GI_TYPE_TAG_UTF8
               || arg->array_elem_tag == GI_TYPE_TAG_FILENAME)
        item = PyUnicode_FromString (((const char **)base)[i]);
      else if (arg->array_elem_tag == GI_TYPE_TAG_INTERFACE)
        {
          GIArgument item_arg = { 0 };
          if (gi_type_info_is_pointer (arg->array_elem_info))
            {
              item_arg.v_pointer = ((gpointer *)base)[i];
            }
          else
            {
              gsize elem_size = gi_type_info_array_element_size (arg->array_elem_info);
              if (elem_size == 0)
                {
                  Py_DECREF (list);
                  PyErr_SetString (PyExc_NotImplementedError,
                                   "callback array interface element size missing");
                  return NULL;
                }
              item_arg.v_pointer = (char *)base + (gsize)i * elem_size;
            }
          item = pygi_argument_to_py_transfer (closure->callback_info,
                                               arg->array_elem_info,
                                               &item_arg,
                                               arg->transfer);
        }
      else
        item = Py_NewRef (Py_None);
      if (item == NULL)
        {
          Py_DECREF (list);
          return NULL;
        }
      PyList_SET_ITEM (list, i, item);
    }
  return list;
}

static int
callback_array_from_py (PyObject *value,
                        PyGICallbackClosure *closure,
                        PyGICallbackArgPlan *arg,
                        void **args,
                        int index)
{
  GITypeTag etag = arg->array_elem_tag;
  if (etag != GI_TYPE_TAG_INT32 && etag != GI_TYPE_TAG_UINT32 && etag != GI_TYPE_TAG_UTF8
      && etag != GI_TYPE_TAG_FILENAME)
    return 0;
  gboolean is_string = etag == GI_TYPE_TAG_UTF8 || etag == GI_TYPE_TAG_FILENAME;
  if (arg->array_length_arg < 0 && !is_string)
    return 0;
  PyObject *seq = PySequence_Fast (value, "expected a sequence");
  if (seq == NULL)
    return -1;
  Py_ssize_t length = PySequence_Fast_GET_SIZE (seq);
  void *items = NULL;
  if (etag == GI_TYPE_TAG_INT32)
    {
      int32_t *buf = g_new0 (int32_t, (gsize)(length > 0 ? length : 1));
      for (Py_ssize_t i = 0; i < length; i++)
        {
          long v = PyLong_AsLong (PySequence_Fast_GET_ITEM (seq, i));
          if (v == -1 && PyErr_Occurred ())
            {
              Py_DECREF (seq);
              g_free (buf);
              return -1;
            }
          buf[i] = (int32_t)v;
        }
      items = buf;
    }
  else if (etag == GI_TYPE_TAG_UINT32)
    {
      uint32_t *buf = g_new0 (uint32_t, (gsize)(length > 0 ? length : 1));
      for (Py_ssize_t i = 0; i < length; i++)
        {
          unsigned long v = PyLong_AsUnsignedLong (PySequence_Fast_GET_ITEM (seq, i));
          if (v == (unsigned long)-1 && PyErr_Occurred ())
            {
              Py_DECREF (seq);
              g_free (buf);
              return -1;
            }
          buf[i] = (uint32_t)v;
        }
      items = buf;
    }
  else /* utf8 / filename */
    {
      /* NULL-terminated strv; size is length+1. */
      char **buf = g_new0 (char *, (gsize)(length + 1));
      for (Py_ssize_t i = 0; i < length; i++)
        {
          PyObject *item = PySequence_Fast_GET_ITEM (seq, i);
          if (item == Py_None)
            continue;
          const char *s = PyUnicode_AsUTF8 (item);
          if (s == NULL)
            {
              Py_DECREF (seq);
              g_strfreev (buf);
              return -1;
            }
          buf[i] = g_strdup (s);
        }
      items = buf;
    }
  Py_DECREF (seq);
  void **slot = *(void ***)args[index];
  if (arg->direction == GI_DIRECTION_INOUT && slot != NULL && *slot != NULL)
    {
      if (is_string)
        g_strfreev ((char **)*slot);
      else
        g_free (*slot);
    }
  if (slot != NULL)
    *slot = items;
  if (arg->array_length_arg >= 0)
    {
      PyGICallbackArgPlan *length_arg = &closure->args[arg->array_length_arg];
      callback_set_length_arg (args, length_arg, arg->array_length_arg, (int)length);
    }
  return 0;
}

static PyObject *
callback_arg_to_py (PyGICallbackClosure *closure,
                    PyGICallbackArgPlan *arg,
                    void **args,
                    int arg_index,
                    void *src)
{
  (void)arg_index;
  GIArgument aligned = { 0 };
  if (src != NULL)
    {
      switch (gi_type_info_storage_tag (arg->type_info))
        {
#define PYGI_SCALAR PYGI_SCALAR_LOAD_ALIGNED_FROM_SRC

#include "marshal/scalar-tags.h"

#undef PYGI_SCALAR

        case GI_TYPE_TAG_UTF8:
        case GI_TYPE_TAG_FILENAME:
          aligned.v_string = *(char **)src;
          break;
        default:
          aligned.v_pointer = *(void **)src;
          break;
        }
    }

  if (arg->tag == GI_TYPE_TAG_VOID)
    {
      if (aligned.v_pointer == NULL)
        Py_RETURN_NONE;
      if (arg->wrapper_gtype != 0)
        return pygi_gobject_to_py_as_gtype ((GObject *)aligned.v_pointer,
                                            arg->wrapper_gtype,
                                            GI_TRANSFER_NOTHING);
      return PyLong_FromVoidPtr (aligned.v_pointer);
    }

  if (arg->tag == GI_TYPE_TAG_INTERFACE && aligned.v_pointer != NULL)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (arg->type_info);
      if (iface != NULL && GI_IS_CALLBACK_INFO (iface))
        {
          gpointer user_data_ptr = NULL;
          unsigned int closure_index = 0;
          if (gi_arg_info_get_closure_index (arg->arg_info, &closure_index)
              && closure_index < (unsigned int)closure->n_args)
            {
              PyGICallbackArgPlan *closure_arg = &closure->args[closure_index];
              void *user_data_src = args[closure_index];
              if (closure_arg->direction == GI_DIRECTION_INOUT && user_data_src != NULL)
                user_data_src = *(void **)user_data_src;
              if (user_data_src != NULL)
                user_data_ptr = *(gpointer *)user_data_src;
            }
          return reverse_callback_new (closure->namespace,
                                       (GICallableInfo *)iface,
                                       aligned.v_pointer,
                                       user_data_ptr);
        }
    }

  if (arg->tag == GI_TYPE_TAG_INTERFACE && arg->transfer == GI_TRANSFER_NOTHING
      && aligned.v_pointer != NULL)
    {
      g_autoptr (GIBaseInfo) iface = gi_type_info_get_interface (arg->type_info);
      if (iface != NULL && (GI_IS_STRUCT_INFO (iface) || GI_IS_UNION_INFO (iface)))
        {
          const char *namespace_name = gi_base_info_get_namespace (iface);
          GType iface_gt = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
          if (iface_gt != G_TYPE_NONE && iface_gt != 0 && G_TYPE_IS_BOXED (iface_gt)
              && g_strcmp0 (namespace_name, "Gst") == 0)
            {
              PyObject *cls = pygi_class_registry_get_pytype_for_gtype (iface_gt);
              if (cls != NULL)
                return pygi_boxed_new_alias (cls, aligned.v_pointer, iface_gt, NULL);
            }
        }
    }

  return pygi_argument_to_py_transfer (closure->callback_info,
                                       arg->type_info,
                                       &aligned,
                                       arg->transfer);
}

static void
callback_trampoline (ffi_cif *cif, void *ret, void **args, void *user_data)
{
  (void)cif;
  PyGICallbackClosure *closure = user_data;
  gboolean defer_async_free = closure->scope == GI_SCOPE_TYPE_ASYNC;
  PyGILState_STATE state = PyGILState_Ensure ();
  PyObject *previous_namespace = NULL;
  if (pygi_enum_push_namespace_context (closure->namespace, &previous_namespace) != 0)
    {
      PyErr_Print ();
      PyGILState_Release (state);
      return;
    }
  /* PyGObject convention: when method.py packs multiple trailing
   * positional args into a `ginext.method._PackedUserData` tuple, the
   * trampoline unpacks them into separate callback positional args. A
   * user-supplied tuple (single positional or user_data= kwarg) stays
   * intact. Size py_args for the worst case so the unpack is in-place. */
  size_t n_py_alloc = (size_t)(closure->n_args > 0 ? closure->n_args : 1);
  gboolean unpack_user_data = FALSE;
  if (closure->py_user_data != NULL && Py_TYPE (closure->py_user_data) != &PyTuple_Type
      && PyTuple_Check (closure->py_user_data))
    {
      /* Subclass-of-tuple: only the private _PackedUserData marker
       * fits the role. Importing the type once is cheap; cache via a
       * static guarded by the closure's first sighting. */
      PyObject *packed_type = pygi_hook_last (pygi_hook_packed_user_data_type);
      if (packed_type != NULL
          && PyObject_TypeCheck (closure->py_user_data, (PyTypeObject *)packed_type))
        {
          unpack_user_data = TRUE;
          Py_ssize_t n_extra = PyTuple_GET_SIZE (closure->py_user_data);
          if (n_extra > 0)
            n_py_alloc += (size_t)n_extra;
        }
    }
  PyObject **py_args = g_new0 (PyObject *, n_py_alloc);
  Py_ssize_t n_py_args = 0;
#define APPEND_PY_ARG(obj)                                                                         \
  do                                                                                               \
    {                                                                                              \
      if ((size_t)n_py_args == n_py_alloc)                                                         \
        {                                                                                          \
          n_py_alloc = n_py_alloc > 0 ? n_py_alloc * 2 : 4;                                        \
          py_args = g_renew (PyObject *, py_args, n_py_alloc);                                     \
        }                                                                                          \
      py_args[n_py_args++] = (obj);                                                                \
    }                                                                                              \
  while (0)
  gboolean expose_array_lengths
      = closure->include_array_length_args || closure->callable_arity < 0
        || closure->callable_arity >= callback_visible_arg_count (closure, TRUE);
  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      if (arg->direction == GI_DIRECTION_OUT)
        continue;
      if (arg->length_owner_array >= 0 && !expose_array_lengths)
        continue;
      if (arg->is_closure
          || (closure->py_user_data == NULL && callback_arg_is_trailing_user_data (closure, i)))
        {
          if (closure->py_user_data != NULL)
            {
              if (unpack_user_data)
                {
                  Py_ssize_t n = PyTuple_GET_SIZE (closure->py_user_data);
                  for (Py_ssize_t k = 0; k < n; k++)
                    APPEND_PY_ARG (Py_NewRef (PyTuple_GET_ITEM (closure->py_user_data, k)));
                }
              else
                APPEND_PY_ARG (Py_NewRef (closure->py_user_data));
            }
          else
            {
              /* A truly omitted closure cookie is hidden from Python.
               * Keep the PyGObject convenience where a fixed-arity
               * callable that explicitly declares the slot can still
               * receive None, but do not leak the slot to variadic
               * callbacks such as `lambda *args: ...`. */
              if (closure->callable_arity >= 0 && closure->callable_arity > n_py_args)
                APPEND_PY_ARG (Py_NewRef (Py_None));
            }
          continue;
        }
      void *src = args[i];
      if (arg->direction == GI_DIRECTION_INOUT)
        src = *(void **)args[i];
      PyObject *py = NULL;
      if (arg->tag == GI_TYPE_TAG_ARRAY)
        py = callback_array_to_py (closure, arg, args, i);
      else
        py = callback_arg_to_py (closure, arg, args, i, src);
      if (py == NULL)
        {
          PyErr_Clear ();
          py = Py_NewRef (Py_None);
        }
      APPEND_PY_ARG (py);
    }
#undef APPEND_PY_ARG

  /* CPython asserts no pending error on entry to PyObject_Vectorcall's
   * frame-init path. If a conversion above smuggled one through, clear
   * it before calling — the failure has already been substituted with
   * None, so the callback can still run. */
  if (PyErr_Occurred ())
    PyErr_Clear ();
  /* Trim trailing args if the callable's positional arity is shorter
   * than the GIR-declared callback signature. Lets `def cb():` bind
   * to a `void cb(gpointer user_data)` GIR shape without TypeError. */
  if (closure->callable_arity >= 0 && (Py_ssize_t)closure->callable_arity < n_py_args)
    {
      for (Py_ssize_t k = (Py_ssize_t)closure->callable_arity; k < n_py_args; k++)
        Py_DECREF (py_args[k]);
      n_py_args = (Py_ssize_t)closure->callable_arity;
    }
  PyObject *result = PyObject_Vectorcall (closure->callable, py_args, (size_t)n_py_args, NULL);
  for (Py_ssize_t i = 0; i < n_py_args; i++)
    Py_DECREF (py_args[i]);
  if (result == NULL)
    {
      PyErr_Print ();
      callback_write_default_value (closure->return_type, closure->return_tag, ret);
      g_free (py_args);
      if (defer_async_free)
        callback_closure_release_py_refs (closure);
      pygi_enum_pop_namespace_context (previous_namespace);
      PyGILState_Release (state);
      if (defer_async_free)
        callback_closure_enqueue_deferred_free (closure);
      return;
    }

  gboolean has_return = closure->return_tag != GI_TYPE_TAG_VOID;
  int total_values = closure->n_out_args + (has_return ? 1 : 0);
  int value_index = 0;
  if (has_return)
    {
      PyObject *ret_value = callback_result_item (result, value_index, total_values);
      if (callback_write_value (ret_value,
                                closure->return_type,
                                closure->return_tag,
                                closure->return_transfer,
                                ret)
          != 0)
        PyErr_Print ();
      else if ((closure->return_tag == GI_TYPE_TAG_UTF8
                || closure->return_tag == GI_TYPE_TAG_FILENAME)
               && closure->return_transfer == GI_TRANSFER_NOTHING)
        {
          /* The caller won't free this string; pin it on the closure
           * so it survives this return but is reclaimed on the next
           * call or teardown. */
          g_clear_pointer (&closure->pinned_return, g_free);
          closure->pinned_return = *(char **)ret;
        }
      value_index++;
    }
  else
    callback_write_direct_value (Py_None,
                                 closure->return_type,
                                 closure->return_tag,
                                 closure->return_transfer,
                                 ret);

  for (int i = 0; i < closure->n_args; i++)
    {
      PyGICallbackArgPlan *arg = &closure->args[i];
      if (arg->direction == GI_DIRECTION_IN)
        continue;
      if (arg->length_owner_array >= 0)
        continue;
      void *slot = *(void **)args[i];
      PyObject *out_value = callback_result_item (result, value_index, total_values);
      if (arg->tag == GI_TYPE_TAG_ARRAY && total_values == 1 && arg->array_length_arg >= 0
          && PyTuple_Check (result) && PyTuple_GET_SIZE (result) == 2)
        {
          PyObject *array_value = PyTuple_GET_ITEM (result, 0);
          if (PySequence_Check (array_value) && !PyUnicode_Check (array_value)
              && !PyBytes_Check (array_value) && !PyByteArray_Check (array_value))
            out_value = array_value;
        }
      if (arg->tag == GI_TYPE_TAG_ARRAY)
        {
          if (callback_array_from_py (out_value, closure, arg, args, i) != 0)
            PyErr_Print ();
        }
      else if (callback_write_value (out_value, arg->type_info, arg->tag, arg->transfer, slot) != 0)
        PyErr_Print ();
      value_index++;
    }
  Py_DECREF (result);
  g_free (py_args);
  if (defer_async_free)
    callback_closure_release_py_refs (closure);
  pygi_enum_pop_namespace_context (previous_namespace);
  PyGILState_Release (state);
  if (defer_async_free)
    callback_closure_enqueue_deferred_free (closure);
}

void
pygi_callback_closure_destroy (gpointer closure)
{
  /* GLib destroy-notify can run from C with the GIL released (e.g. while a
   * GMainLoop is polling). The closure owns Python references, so always
   * reacquire before freeing it. */
  PyGILState_STATE state = PyGILState_Ensure ();
  callback_closure_free ((PyGICallbackClosure *)closure);
  PyGILState_Release (state);
}

void
pygi_callback_closure_set_py_user_data (gpointer closure, PyObject *user_data)
{
  PyGICallbackClosure *cb = closure;
  if (cb == NULL)
    return;
  Py_XDECREF (cb->py_user_data);
  cb->py_user_data = Py_XNewRef (user_data);
}

int
pygi_callback_closure_new (PyObject *callable,
                           GIBaseInfo *callback_info,
                           GIScopeType scope,
                           GIArgument *dest,
                           PyGIArgCleanup *cleanup)
{
  pygi_callback_closure_drain_deferred_frees ();

  if (callable == Py_None)
    {
      dest->v_pointer = NULL;
      cleanup->kind = PYGI_ARG_CLEANUP_NONE;
      return 0;
    }
  if (!PyCallable_Check (callable))
    {
      PyErr_SetString (PyExc_TypeError, "callback argument must be callable or None");
      return -1;
    }
  PyGICallbackClosure *closure = callback_closure_alloc (callable, (GICallableInfo *)callback_info);
  closure->scope = scope;
  if (ffi_prep_cif (&closure->cif,
                    FFI_DEFAULT_ABI,
                    (unsigned)closure->n_args,
                    closure->ffi_return_type,
                    closure->ffi_arg_types)
      != FFI_OK)
    {
      callback_closure_free (closure);
      PyErr_SetString (PyExc_RuntimeError, "ffi_prep_cif failed");
      return -1;
    }
  closure->closure = ffi_closure_alloc (sizeof (ffi_closure), &closure->code);
  if (closure->closure == NULL)
    {
      callback_closure_free (closure);
      PyErr_NoMemory ();
      return -1;
    }
  if (ffi_prep_closure_loc (closure->closure,
                            &closure->cif,
                            callback_trampoline,
                            closure,
                            closure->code)
      != FFI_OK)
    {
      callback_closure_free (closure);
      PyErr_SetString (PyExc_RuntimeError, "ffi_prep_closure_loc failed");
      return -1;
    }

  dest->v_pointer = closure->code;
  cleanup->ptr = closure;
  cleanup->kind
      = scope == GI_SCOPE_TYPE_CALL ? PYGI_ARG_CLEANUP_FFI_CLOSURE : PYGI_ARG_CLEANUP_NONE;
  return 0;
}

int
pygi_vfunc_closure_new (PyObject *callable,
                        GIBaseInfo *callback_info,
                        GIArgument *dest,
                        PyGIArgCleanup *cleanup)
{
  return pygi_callback_closure_new (callable, callback_info, GI_SCOPE_TYPE_NOTIFIED, dest, cleanup);
}

/* pygi_closure_new / pygi_closure_new_with_kind / pygi_closure_new_for_signal*
 * live in GObject/Closure-signal.c. pygi_callback_closure_* (for GIR callback
 * args) remain stubbed here pending slice 0c. */

PyType_Slot ReverseCallback_slots[] = {
  { Py_tp_dealloc, (void *)reverse_callback_dealloc },
  { Py_tp_call, (void *)reverse_callback_call },
  { Py_tp_repr, (void *)reverse_callback_repr },
  { 0, NULL },
};

PyType_Spec ReverseCallback_spec = {
  .name = "ginext.private._gobject.CallbackWrapper",
  .basicsize = sizeof (PyGIReverseCallback),
  .flags = Py_TPFLAGS_DEFAULT,
  .slots = ReverseCallback_slots,
};
