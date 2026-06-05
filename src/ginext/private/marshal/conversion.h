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
#include <glib-object.h>
#include <stdbool.h>

#include "invoke/arg-cleanup.h"

/* PyGIType */

typedef enum
{
  PYGI_TYPE_UNSUPPORTED = 0,
  PYGI_TYPE_VOID,
  PYGI_TYPE_POINTER,
  PYGI_TYPE_BOOLEAN,
  PYGI_TYPE_INT8,
  PYGI_TYPE_UINT8,
  PYGI_TYPE_INT16,
  PYGI_TYPE_UINT16,
  PYGI_TYPE_INT32,
  PYGI_TYPE_UINT32,
  PYGI_TYPE_INT64,
  PYGI_TYPE_UINT64,
  PYGI_TYPE_FLOAT,
  PYGI_TYPE_DOUBLE,
  PYGI_TYPE_UNICHAR,
  PYGI_TYPE_UTF8,
  PYGI_TYPE_FILENAME,
  PYGI_TYPE_GTYPE,
  PYGI_TYPE_ENUM,
  PYGI_TYPE_FLAGS,
  PYGI_TYPE_OBJECT,
  PYGI_TYPE_BOXED,
  PYGI_TYPE_VARIANT,
  PYGI_TYPE_INTERFACE,
  PYGI_TYPE_CALLBACK,
  PYGI_TYPE_ARRAY,
  PYGI_TYPE_GLIST,
  PYGI_TYPE_GSLIST,
  PYGI_TYPE_GHASH,
  PYGI_TYPE_ERROR,
} PyGITypeKind;

typedef struct
{
  PyGITypeKind kind;
  GITypeTag gi_tag;
  GITransfer transfer;
  GType gtype;
  bool is_pointer;
  bool nullable;
  bool caller_allocates;
} PyGIType;

typedef enum
{
  PYGI_VALUE_STORAGE_GIARG,
  PYGI_VALUE_STORAGE_GVALUE,
  PYGI_VALUE_STORAGE_MEMORY,
} PyGIValueStorage;

typedef struct
{
  const PyGIType *type;
  PyGIValueStorage storage;
  union
  {
    GIArgument *giarg;
    GValue *gvalue;
    void *memory;
  } as;
} PyGIValue;

int
pygi_type_from_gi (GITypeInfo *ti, PyGIType *out);
int
pygi_type_from_gi_tag (GITypeTag tag, bool is_pointer, PyGIType *out);
int
pygi_type_from_gtype (GType gtype, PyGIType *out);
int
pygi_type_from_gvalue (const GValue *value, PyGIType *out);
bool
pygi_type_is_direct_storage (const PyGIType *type);
gsize
pygi_type_storage_size (const PyGIType *type);

/* GType */

int
pygi_gtype_from_gimeta_attr (PyObject *obj, GType *out);
int
pygi_gtype_from_py_object (PyObject *obj, GType *out);
PyObject *
pygi_gtype_value_to_py (GType gtype);

/* PyGIValue */

PyGIValue
pygi_value_for_giarg (const PyGIType *type, GIArgument *arg);
PyGIValue
pygi_value_for_gvalue (const PyGIType *type, GValue *value);
PyGIValue
pygi_value_for_memory (const PyGIType *type, void *memory);
int
pygi_value_from_py (PyObject *py, PyGIValue *out);
PyObject *
pygi_value_to_py (const PyGIValue *value);

/* GValue */

int
pygi_gvalue_from_py (PyObject *h, GIArgInfo *arg_info, GIArgument *out, PyGIArgCleanup *cleanup);
int
pygi_py_to_gvalue_inplace (PyObject *h, GValue *value, GIArgInfo *arg_info);
int
pygi_py_to_gvalue_targeted (GType target, PyObject *obj, GValue *value, const char *context);
PyObject *
pygi_gvalue_to_py (GIArgument *arg);
PyObject *
pygi_gvalue_value_to_py (GValue *value);

/* GObject.Value */

int
pygi_gvalue_wrapper_get (PyObject *obj, GValue **out);
int
pygi_py_to_gvalue_property (PyObject *py_value, GValue *out);
