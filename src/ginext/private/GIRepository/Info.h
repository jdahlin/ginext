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

/* Native CPython wrappers for the GIRepository GIBaseInfo hierarchy.
 *
 * Each GIRepository.*Info type lives in its own translation unit
 * (BaseInfo.c, ObjectInfo.c, ValueInfo.c, …). They all share this storage
 * layout — subtypes differ only by their PyTypeObject and tp_base chain,
 * never by fields. The wrapped GIBaseInfo* is owned: reffed on wrap,
 * unreffed on dealloc.
 *
 * Defining the hierarchy as CPython types (rather than building it from the
 * GIRepository-3.0 typelib) breaks the bootstrap cycle: wrapping a
 * GIBaseInfo* no longer needs the typelib classes that wrapping itself would
 * have to construct. */
typedef struct
{
  PyObject_HEAD GIBaseInfo *info;
} PyGIBaseInfo;

#define PYGI_INFO(self) (((PyGIBaseInfo *)(self))->info)

/* ── self-only scalar getter codegen ─────────────────────────────────────────
 *
 * libgirepository's `gi_<infix>_<method>(GI<Type> *info)` getters follow a
 * regular naming scheme, so each type's .c declares an X-macro list and
 * expands it twice — once with INFO_EMIT_FN to define the PyCFunction bodies,
 * once with INFO_EMIT_DEF to fill the PyMethodDef table. Each list entry is
 * `X(KIND, infix, method, GIType)`:
 *   KIND  — return marshalling (STR / BOOL / UINT / SIZE / GTYPE / INT)
 *   infix — the gi_<infix>_ function-name segment (e.g. object_info)
 *   GIType— the pointer cast for the gi call (e.g. GIObjectInfo)
 *
 * Only self-only getters belong here; index getters, out-param getters and the
 * convenience properties are hand-written in the owning .c file. */

#define INFO_FN_STR(infix, method, GIType)                                                         \
  static PyObject *infofn_##infix##_##method (PyObject *self, PyObject *Py_UNUSED (a))             \
  {                                                                                                \
    const char *s = gi_##infix##_##method ((GIType *)PYGI_INFO (self));                            \
    return PyUnicode_FromString (s ? s : "");                                                      \
  }
#define INFO_FN_BOOL(infix, method, GIType)                                                        \
  static PyObject *infofn_##infix##_##method (PyObject *self, PyObject *Py_UNUSED (a))             \
  {                                                                                                \
    return PyBool_FromLong (gi_##infix##_##method ((GIType *)PYGI_INFO (self)));                   \
  }
#define INFO_FN_UINT(infix, method, GIType)                                                        \
  static PyObject *infofn_##infix##_##method (PyObject *self, PyObject *Py_UNUSED (a))             \
  {                                                                                                \
    return PyLong_FromUnsignedLong (gi_##infix##_##method ((GIType *)PYGI_INFO (self)));           \
  }
#define INFO_FN_SIZE(infix, method, GIType)                                                        \
  static PyObject *infofn_##infix##_##method (PyObject *self, PyObject *Py_UNUSED (a))             \
  {                                                                                                \
    return PyLong_FromSize_t (gi_##infix##_##method ((GIType *)PYGI_INFO (self)));                 \
  }
#define INFO_FN_GTYPE(infix, method, GIType)                                                       \
  static PyObject *infofn_##infix##_##method (PyObject *self, PyObject *Py_UNUSED (a))             \
  {                                                                                                \
    return PyLong_FromUnsignedLongLong (                                                           \
        (unsigned long long)gi_##infix##_##method ((GIType *)PYGI_INFO (self)));                   \
  }
#define INFO_FN_INT(infix, method, GIType)                                                         \
  static PyObject *infofn_##infix##_##method (PyObject *self, PyObject *Py_UNUSED (a))             \
  {                                                                                                \
    return PyLong_FromLong ((long)gi_##infix##_##method ((GIType *)PYGI_INFO (self)));             \
  }

/* Return-type annotations for __text_signature__ — one per KIND. */
#define INFO_RETURN_TYPE_STR   "str"
#define INFO_RETURN_TYPE_BOOL  "bool"
#define INFO_RETURN_TYPE_UINT  "int"
#define INFO_RETURN_TYPE_SIZE  "int"
#define INFO_RETURN_TYPE_GTYPE "int"
#define INFO_RETURN_TYPE_INT   "int"

#define INFO_EMIT_FN(KIND, infix, method, GIType) INFO_FN_##KIND (infix, method, GIType)

/* PyMethodDef entry.  The docstring slot carries a __text_signature__ so that
 * inspect.signature() returns a typed signature (e.g. ``($self, /) -> str``)
 * without any hand-written .pyi file.  The ``\n--\n\n`` separator is the CPython
 * convention that splits signature from human-readable docstring. */
#define INFO_EMIT_DEF(KIND, infix, method, GIType)                                                 \
  { #method, infofn_##infix##_##method, METH_NOARGS,                                               \
    "($self, /) -> " INFO_RETURN_TYPE_##KIND "\n--\n\n" },

/* Define a PyTypeObject deriving from `basetype`. tp_new / tp_dealloc / tp_repr
 * are inherited from PyGIBaseInfo_Type via PyType_Ready, so subtype files only
 * supply their method/getset tables. Non-static so the dispatcher and the
 * registrar (Info.c) can reference the type by name. */
#define INFO_TYPE(CName, pyname, basetype, methods, getset)                                        \
  PyTypeObject CName = {                                                                           \
    PyVarObject_HEAD_INIT (NULL, 0).tp_name = "ginext.GIRepository." pyname,                       \
    .tp_basicsize = sizeof (PyGIBaseInfo),                                                         \
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,                                          \
    .tp_methods = methods,                                                                         \
    .tp_getset = getset,                                                                           \
    .tp_base = basetype,                                                                           \
  }

/* Empty getter list, for types that add no self-only scalar getters. */
#define INFO_NO_GETTERS(X)

/* One-shot type definition: expand GETTERS into getter bodies, build the
 * <CName>_methods table from them, and define the type. `getset` is a
 * PyGetSetDef[] or NULL. This is the whole body of a per-type .c file. */
#define INFO_DEFINE_TYPE(CName, pyname, basetype, GETTERS, getset)                                 \
  GETTERS (INFO_EMIT_FN)                                                                           \
  static PyMethodDef CName##_methods[] = { GETTERS (INFO_EMIT_DEF){ 0 } };                          \
  INFO_TYPE (CName, pyname, basetype, CName##_methods, getset)

/* Convenience-property bodies (for tp_getset). FWD forwards to a
 * helper(GIType*); STR/GTYPE mirror the scalar getter marshalling. */
#define INFO_PROP_FWD(propfn, helper, GIType)                                                      \
  static PyObject *propfn (PyObject *self, void *Py_UNUSED (closure))                              \
  {                                                                                                \
    return helper ((GIType *)PYGI_INFO (self));                                                    \
  }
#define INFO_PROP_STR(propfn, gifn, GIType)                                                        \
  static PyObject *propfn (PyObject *self, void *Py_UNUSED (closure))                              \
  {                                                                                                \
    const char *s = gifn ((GIType *)PYGI_INFO (self));                                             \
    return PyUnicode_FromString (s ? s : "");                                                      \
  }
#define INFO_PROP_GTYPE(propfn, gifn, GIType)                                                      \
  static PyObject *propfn (PyObject *self, void *Py_UNUSED (closure))                              \
  {                                                                                                \
    return PyLong_FromUnsignedLongLong ((unsigned long long)gifn ((GIType *)PYGI_INFO (self)));    \
  }

/* The hierarchy. Each is defined in the matching <Name>.c. */
extern PyTypeObject PyGIBaseInfo_Type;
extern PyTypeObject PyGICallableInfo_Type;
extern PyTypeObject PyGIFunctionInfo_Type;
extern PyTypeObject PyGISignalInfo_Type;
extern PyTypeObject PyGIVFuncInfo_Type;
extern PyTypeObject PyGICallbackInfo_Type;
extern PyTypeObject PyGIRegisteredTypeInfo_Type;
extern PyTypeObject PyGIObjectInfo_Type;
extern PyTypeObject PyGIInterfaceInfo_Type;
extern PyTypeObject PyGIStructInfo_Type;
extern PyTypeObject PyGIUnionInfo_Type;
extern PyTypeObject PyGIEnumInfo_Type;
extern PyTypeObject PyGIFlagsInfo_Type;
extern PyTypeObject PyGIConstantInfo_Type;
extern PyTypeObject PyGIPropertyInfo_Type;
extern PyTypeObject PyGIArgInfo_Type;
extern PyTypeObject PyGIFieldInfo_Type;
extern PyTypeObject PyGITypeInfo_Type;
extern PyTypeObject PyGIValueInfo_Type;
extern PyTypeObject PyGIUnresolvedInfo_Type;

/* Shared dealloc — unrefs the wrapped info. BaseInfo installs it; subtypes
 * inherit it. Exposed so any future per-type override can chain to it. */
void
ginext_info_dealloc (PyObject *self);

/* Wrap a GIBaseInfo* as the most specific native type (dispatched on the
 * GI_IS_*_INFO predicates). Takes its own ref; the caller keeps theirs. */
PyObject *
pygi_base_info_wrap (GIBaseInfo *info);

/* PyType_Ready every type in the hierarchy and add them to `module`. */
int
ginext_register_info_types (PyObject *module);

/* Core helpers implemented next to the C functions they reuse, called by the
 * native getset properties in the owning .c files. */
PyObject *
ginext_constant_info_value (GIConstantInfo *info);
PyObject *
ginext_callable_info_arg_names (GICallableInfo *info);
PyObject *
ginext_callable_info_has_user_data_slot (GICallableInfo *info);

/* Method implementations (in namespace.c) shared by the types that expose
 * them: object_info on ObjectInfo+InterfaceInfo, record_info / find_method on
 * StructInfo+UnionInfo. Each takes the info instance as self. */
PyObject *
ginext_object_info_method (PyObject *self, PyObject *args);
PyObject *
ginext_record_info_method (PyObject *self, PyObject *args);
PyObject *
ginext_find_method_method (PyObject *self, PyObject *args);
/* anonymous_union_offset on StructInfo+UnionInfo (implemented in shims.c). */
PyObject *
ginext_anonymous_union_offset_method (PyObject *self, PyObject *args);
