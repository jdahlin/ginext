#pragma once
#include <Python.h>

/* Each hook is a slot in pygi_hooks[]; the enum gives each a stable integer
 * index.  Keep entries sorted by their string name (used for bsearch in
 * py_register_hook).  PYGI_HOOK_COUNT must remain last. */
typedef enum
{
  PYGI_HOOK_CALLABLE_SIGNATURE = 0,
  PYGI_HOOK_CLASS_FROM_NS_PROFILE,
  PYGI_HOOK_EXCEPTION_FROM_GERROR,
  PYGI_HOOK_FUNDAMENTAL_GETATTR,
  PYGI_HOOK_GVALUE_FROM_PY,
  PYGI_HOOK_GVALUE_TO_PY,
  PYGI_HOOK_LOAD_NAMESPACE,
  PYGI_HOOK_OBJECT_GETATTR,
  PYGI_HOOK_OBJECT_POST_INIT,
  PYGI_HOOK_OBJECT_SETATTR,
  PYGI_HOOK_OBJECT_WRAP,
  PYGI_HOOK_OBJECTCLASS_DIR,
  PYGI_HOOK_OBJECTCLASS_GETATTR,
  PYGI_HOOK_PACKED_USER_DATA_TYPE,
  PYGI_HOOK_RESULT_TUPLE_NEW_TYPE,
  PYGI_HOOK_COUNT,
} PyGIHookID;

/* Each element is a PyList (possibly NULL if no handlers registered yet). */
extern PyObject *pygi_hooks[PYGI_HOOK_COUNT];

/* Shorthands so existing call sites in C don't need renaming. */
#define pygi_hook_callable_signature           pygi_hooks[PYGI_HOOK_CALLABLE_SIGNATURE]
#define pygi_hook_class_from_namespace_profile pygi_hooks[PYGI_HOOK_CLASS_FROM_NS_PROFILE]
#define pygi_hook_exception_from_gerror        pygi_hooks[PYGI_HOOK_EXCEPTION_FROM_GERROR]
#define pygi_hook_gvalue_from_py               pygi_hooks[PYGI_HOOK_GVALUE_FROM_PY]
#define pygi_hook_gvalue_to_py                 pygi_hooks[PYGI_HOOK_GVALUE_TO_PY]
#define pygi_hook_load_namespace               pygi_hooks[PYGI_HOOK_LOAD_NAMESPACE]
#define pygi_hook_method_for_instance          pygi_hooks[PYGI_HOOK_FUNDAMENTAL_GETATTR]
#define pygi_hook_finish_construction          pygi_hooks[PYGI_HOOK_OBJECT_POST_INIT]
#define pygi_hook_obj_getattr                  pygi_hooks[PYGI_HOOK_OBJECT_GETATTR]
#define pygi_hook_obj_setattr                  pygi_hooks[PYGI_HOOK_OBJECT_SETATTR]
#define pygi_hook_object_wrap                  pygi_hooks[PYGI_HOOK_OBJECT_WRAP]
#define pygi_hook_gobjectmeta_getattr          pygi_hooks[PYGI_HOOK_OBJECTCLASS_GETATTR]
#define pygi_hook_gobjectmeta_dir              pygi_hooks[PYGI_HOOK_OBJECTCLASS_DIR]
#define pygi_hook_packed_user_data_type        pygi_hooks[PYGI_HOOK_PACKED_USER_DATA_TYPE]
#define pygi_hook_result_tuple_new_type        pygi_hooks[PYGI_HOOK_RESULT_TUPLE_NEW_TYPE]

/* Return a borrowed ref to the last-registered handler, or NULL (no error set). */
static inline PyObject *
pygi_hook_last (PyObject *list)
{
  if (list == NULL || !PyList_Check (list) || PyList_GET_SIZE (list) == 0)
    return NULL;
  return PyList_GET_ITEM (list, PyList_GET_SIZE (list) - 1);
}

/* Call handlers in reverse-registration order; return first non-NULL result.
 * On AttributeError from a handler, continue.  On any other error, stop and
 * propagate.  If list is NULL/empty or all raised AttributeError, sets
 * AttributeError and returns NULL. */
PyObject *pygi_hook_call_first (PyObject *list, PyObject *args);

/* Call ALL handlers in registration order; ignore return values.
 * Stops and propagates on any exception.
 * Returns 0 on success, -1 on error. */
int pygi_hook_call_all (PyObject *list, PyObject *args);
