// hooks.c
#include <Python.h>
#include "hooks.h"

/* Array of hook lists; each element is a PyList or NULL.
 * Zero-initialized by C. */
PyObject *pygi_hooks[PYGI_HOOK_COUNT];

/* Call handlers in reverse-registration order; return first non-NULL result.
 * On AttributeError from a handler, continue to the next.
 * On any other error, stop and propagate.
 * If list is NULL/empty or all raised AttributeError, sets AttributeError
 * and returns NULL. */
PyObject *
pygi_hook_call_first (PyObject *list, PyObject *args)
{
  if (list == NULL || !PyList_Check (list))
    {
      PyErr_SetString (PyExc_AttributeError, "no hook registered");
      return NULL;
    }
  Py_ssize_t n = PyList_GET_SIZE (list);
  if (n == 0)
    {
      PyErr_SetString (PyExc_AttributeError, "no hook registered");
      return NULL;
    }
  for (Py_ssize_t i = n - 1; i >= 0; i--)
    {
      PyObject *handler = PyList_GET_ITEM (list, i);
      PyObject *result = PyObject_Call (handler, args, NULL);
      if (result != NULL)
        return result;
      if (!PyErr_ExceptionMatches (PyExc_AttributeError))
        return NULL; /* propagate non-AttributeError */
      PyErr_Clear ();
    }
  PyErr_SetString (PyExc_AttributeError, "no hook handled the call");
  return NULL;
}

/* Call ALL handlers in registration order; ignore return values.
 * Stops and propagates on any exception.
 * Returns 0 on success, -1 on error. */
int
pygi_hook_call_all (PyObject *list, PyObject *args)
{
  if (list == NULL || !PyList_Check (list))
    return 0;
  Py_ssize_t n = PyList_GET_SIZE (list);
  for (Py_ssize_t i = 0; i < n; i++)
    {
      PyObject *handler = PyList_GET_ITEM (list, i);
      PyObject *result = PyObject_Call (handler, args, NULL);
      if (result != NULL)
        {
          Py_DECREF (result);
          continue;
        }
      return -1;
    }
  return 0;
}
