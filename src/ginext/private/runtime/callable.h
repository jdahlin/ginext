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

#include <Python.h>

#include <girepository/girepository.h>

typedef struct PyGICompiledCallable PyGICompiledCallable;

typedef struct
{
  PyObject_HEAD PyGICompiledCallable *compiled;
  vectorcallfunc vectorcall;
  GIFunctionInfo *info;
  int has_self;
  char *qualified_name;
  PyObject *gimeta;
  PyObject *name;
  PyObject *qualname;
  PyObject *module;
  PyObject *doc;
  PyObject *defaults;
  PyObject *kwdefaults;
  PyObject *annotations;
  PyObject *annotate;
  PyObject *type_params;
  PyObject *objclass;
  /* Python Namespace object that created this descriptor. Used by return
   * marshalling to resolve enum/flags wrapper classes for the same ABI
   * profile as the callable owner. Owned. */
  PyObject *namespace;
  /* Cached for the C kwarg-merge + user_data-peel path in
   * py_invoke_callable_descriptor. arg_names is a tuple of str with the
   * pygobject dash-to-underscore conversion already applied (visible args
   * only — closure/length companions skipped, matching the surface that
   * Python sees). Owned. */
  PyObject *arg_names;
  /* True iff the callable has a callback arg whose `closure` annotation
   * points at a separate user_data slot (the pygobject-compat surface
   * where trailing positionals / user_data= kwarg pack into that slot). */
  int has_user_data_slot;
  /* Number of closure companion args that are elided from the default
   * Python surface (role == CLOSURE_DESTROY). When the caller supplies
   * exactly this many extra args beyond the visible surface, they are
   * passed through as individual positionals rather than packed into
   * _PackedUserData — they explicitly fill each closure slot. */
  Py_ssize_t n_elided_closures;
} PyGICallableDescriptor;

extern PyTypeObject *ginext_callable_descriptor_type;
extern PyType_Spec GinextCallableDescriptor_spec;

void
pygi_describe_callable_shape (GICallableInfo *cb, int has_self, char *buf, size_t buf_size);
PyObject *
pygi_unsupported_fallback_shape (const char *qualified_name,
                                 GICallableInfo *cb,
                                 const char *detail);

PyGICompiledCallable *
pygi_compile_callable_for_ffi_target (GICallableInfo *callable,
                                      void *target,
                                      int has_self,
                                      const char *qualified_name);

void
pygi_compiled_callable_destroy_for_ffi (PyGICompiledCallable *compiled);
