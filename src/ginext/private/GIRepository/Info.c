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

/* GIRepository.*Info dispatch and registration. The types themselves live one
 * per file (BaseInfo.c, ObjectInfo.c, ValueInfo.c, …); this file only maps a
 * GIBaseInfo* to its native type and stands the hierarchy up at module init. */

#include "GIRepository/Info.h"

#include <string.h>

/* Most specific first: a GIFlagsInfo is-a GIEnumInfo, a GIFunctionInfo is-a
 * GICallableInfo, every registered type is-a GIRegisteredTypeInfo. */
static PyTypeObject *
type_for_info (GIBaseInfo *info)
{
  if (GI_IS_FUNCTION_INFO (info))
    return &PyGIFunctionInfo_Type;
  if (GI_IS_SIGNAL_INFO (info))
    return &PyGISignalInfo_Type;
  if (GI_IS_VFUNC_INFO (info))
    return &PyGIVFuncInfo_Type;
  if (GI_IS_CALLBACK_INFO (info))
    return &PyGICallbackInfo_Type;
  if (GI_IS_CALLABLE_INFO (info))
    return &PyGICallableInfo_Type;
  if (GI_IS_OBJECT_INFO (info))
    return &PyGIObjectInfo_Type;
  if (GI_IS_INTERFACE_INFO (info))
    return &PyGIInterfaceInfo_Type;
  if (GI_IS_STRUCT_INFO (info))
    return &PyGIStructInfo_Type;
  if (GI_IS_UNION_INFO (info))
    return &PyGIUnionInfo_Type;
  if (GI_IS_FLAGS_INFO (info))
    return &PyGIFlagsInfo_Type;
  if (GI_IS_ENUM_INFO (info))
    return &PyGIEnumInfo_Type;
  if (GI_IS_REGISTERED_TYPE_INFO (info))
    return &PyGIRegisteredTypeInfo_Type;
  if (GI_IS_CONSTANT_INFO (info))
    return &PyGIConstantInfo_Type;
  if (GI_IS_PROPERTY_INFO (info))
    return &PyGIPropertyInfo_Type;
  if (GI_IS_ARG_INFO (info))
    return &PyGIArgInfo_Type;
  if (GI_IS_FIELD_INFO (info))
    return &PyGIFieldInfo_Type;
  if (GI_IS_TYPE_INFO (info))
    return &PyGITypeInfo_Type;
  if (GI_IS_VALUE_INFO (info))
    return &PyGIValueInfo_Type;
  if (GI_IS_UNRESOLVED_INFO (info))
    return &PyGIUnresolvedInfo_Type;
  return &PyGIBaseInfo_Type;
}

PyObject *
pygi_base_info_wrap (GIBaseInfo *info)
{
  if (info == NULL)
    Py_RETURN_NONE;
  PyTypeObject *type = type_for_info (info);
  PyGIBaseInfo *self = PyObject_New (PyGIBaseInfo, type);
  if (self == NULL)
    return NULL;
  self->info = gi_base_info_ref (info);
  return (PyObject *)self;
}

/* __match_args__ for structural pattern matching. Set the salient attributes
 * (name first) on each tier of the hierarchy and let the leaves inherit them
 * by ordinary attribute lookup — FunctionInfo from CallableInfo, FlagsInfo
 * from EnumInfo, ObjectInfo/StructInfo/… from RegisteredTypeInfo — so user
 * code can write `case ConstantInfo(name, value)` or `case EnumInfo(name,
 * members)`. These are static types, which reject the Python-level
 * `Type.__match_args__ = …`; writing tp_dict from C (after PyType_Ready) is
 * how CPython attaches __match_args__ to its own static types. */
static int
info_set_match_args (PyTypeObject *type, const char *const *names, Py_ssize_t n)
{
  PyObject *tuple = PyTuple_New (n);
  if (tuple == NULL)
    return -1;
  for (Py_ssize_t i = 0; i < n; i++)
    {
      PyObject *name = PyUnicode_FromString (names[i]);
      if (name == NULL)
        {
          Py_DECREF (tuple);
          return -1;
        }
      PyTuple_SET_ITEM (tuple, i, name);
    }
  int rc = PyDict_SetItemString (type->tp_dict, "__match_args__", tuple);
  Py_DECREF (tuple);
  if (rc == 0)
    PyType_Modified (type);
  return rc;
}

#define INFO_SET_MATCH_ARGS(type, ...)                                                             \
  do                                                                                               \
    {                                                                                              \
      const char *const _names[] = { __VA_ARGS__ };                                                \
      if (info_set_match_args (&(type),                                                            \
                               _names,                                                             \
                               (Py_ssize_t)(sizeof (_names) / sizeof (_names[0])))                 \
          < 0)                                                                                     \
        return -1;                                                                                 \
    }                                                                                              \
  while (0)

int
ginext_register_info_types (PyObject *module)
{
  /* Base types must be readied before the leaves that derive from them. */
  PyTypeObject *types[] = {
    &PyGIBaseInfo_Type,     &PyGICallableInfo_Type,   &PyGIRegisteredTypeInfo_Type,
    &PyGIFunctionInfo_Type, &PyGISignalInfo_Type,     &PyGIVFuncInfo_Type,
    &PyGICallbackInfo_Type, &PyGIObjectInfo_Type,     &PyGIInterfaceInfo_Type,
    &PyGIStructInfo_Type,   &PyGIUnionInfo_Type,      &PyGIEnumInfo_Type,
    &PyGIFlagsInfo_Type,    &PyGIConstantInfo_Type,   &PyGIPropertyInfo_Type,
    &PyGIArgInfo_Type,      &PyGIFieldInfo_Type,      &PyGITypeInfo_Type,
    &PyGIValueInfo_Type,    &PyGIUnresolvedInfo_Type,
  };
  size_t n = sizeof (types) / sizeof (types[0]);
  for (size_t i = 0; i < n; i++)
    {
      if (PyType_Ready (types[i]) < 0)
        return -1;
    }
  INFO_SET_MATCH_ARGS (PyGIBaseInfo_Type, "name", "namespace");
  INFO_SET_MATCH_ARGS (PyGICallableInfo_Type, "name", "arg_names");
  INFO_SET_MATCH_ARGS (PyGIRegisteredTypeInfo_Type, "name", "gtype");
  INFO_SET_MATCH_ARGS (PyGIEnumInfo_Type, "name", "members");
  INFO_SET_MATCH_ARGS (PyGIConstantInfo_Type, "name", "value");

  /* Property aliases: expose .name/.namespace/.gtype/etc. as thin property
   * wrappers over the typed get_*() methods. C extension types are immutable
   * from Python so we inject these into tp_dict here, after PyType_Ready. */
#define INFO_SET_PROP(type, attr, method)                                                          \
  do                                                                                               \
    {                                                                                              \
      PyObject *_fn = PyObject_GetAttrString ((PyObject *)&(type), method);                        \
      if (_fn == NULL) return -1;                                                                   \
      PyObject *_prop = PyObject_CallOneArg ((PyObject *)&PyProperty_Type, _fn);                   \
      Py_DECREF (_fn);                                                                             \
      if (_prop == NULL) return -1;                                                                \
      int _rc = PyDict_SetItemString ((type).tp_dict, attr, _prop);                               \
      Py_DECREF (_prop);                                                                           \
      if (_rc < 0) return -1;                                                                     \
      PyType_Modified (&(type));                                                                   \
    }                                                                                              \
  while (0)

  INFO_SET_PROP (PyGIBaseInfo_Type, "name", "get_name");
  INFO_SET_PROP (PyGIBaseInfo_Type, "namespace", "get_namespace");
  INFO_SET_PROP (PyGIRegisteredTypeInfo_Type, "gtype", "get_g_type");
  INFO_SET_PROP (PyGIEnumInfo_Type, "members", "get_members");
  INFO_SET_PROP (PyGIConstantInfo_Type, "value", "get_value");
  INFO_SET_PROP (PyGICallableInfo_Type, "arg_names", "get_arg_names");
  INFO_SET_PROP (PyGICallableInfo_Type, "has_user_data_slot", "get_has_user_data_slot");
  for (size_t i = 0; i < n; i++)
    {
      const char *dot = strrchr (types[i]->tp_name, '.');
      const char *short_name = dot ? dot + 1 : types[i]->tp_name;
      Py_INCREF (types[i]);
      if (PyModule_AddObject (module, short_name, (PyObject *)types[i]) < 0)
        {
          Py_DECREF (types[i]);
          return -1;
        }
    }
  return 0;
}
