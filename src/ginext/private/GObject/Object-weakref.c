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

/* GObject.weak_ref(callback, *args) implementation.
 *
 * Returns a GObjectWeakRef that:
 *   - fires callback(*args) when the GObject is finalized
 *   - holds a self-reference so it survives even if the Python caller drops it
 *   - has .unref() to cancel the notification early
 *   - is callable (callable() returns True) for API symmetry with the no-callback form
 */

#include "common.h"
#include "Object.h"
#include "Object-info.h"
#include "Object-weakref.h"

typedef struct
{
  PyObject_HEAD
  GObject *object;    /* raw pointer, NOT ref-counted; NULL after notify fires */
  PyObject *callback; /* Python callable */
  PyObject *args;     /* tuple of extra args */
  int cancelled;      /* set by unref() */
} GinextGObjectWeakRef;

static void
weakref_notify (gpointer data, GObject *where_the_object_was G_GNUC_UNUSED)
{
  PyGILState_STATE state = PyGILState_Ensure ();
  GinextGObjectWeakRef *self = (GinextGObjectWeakRef *)data;

  self->object = NULL;

  if (!self->cancelled && self->callback != NULL)
    {
      PyObject *result = PyObject_Call (self->callback, self->args, NULL);
      if (result == NULL)
        PyErr_Print ();
      else
        Py_DECREF (result);
    }

  /* Drop the self-reference the constructor took. */
  Py_DECREF (self);
  PyGILState_Release (state);
}

static void
weakref_dealloc (GinextGObjectWeakRef *self)
{
  /* If the GObject is still alive and the notify wasn't cancelled, unregister. */
  if (self->object != NULL && !self->cancelled)
    {
      g_object_weak_unref (self->object, weakref_notify, self);
      /* weakref_notify won't fire so we drop the self-ref it would have dropped. */
      Py_DECREF (self);
    }
  Py_XDECREF (self->callback);
  Py_XDECREF (self->args);
  PyObject_Free (self);
}

static PyObject *
weakref_call (GinextGObjectWeakRef *self, PyObject *args G_GNUC_UNUSED,
              PyObject *kwargs G_GNUC_UNUSED)
{
  /* Calling the weakref returns the wrapped GObject (or None if gone). */
  if (self->object == NULL)
    Py_RETURN_NONE;
  PyObject *wrapper = pygi_gobject_new ((PyObject *)pygi_gobject_type, self->object, 0);
  return wrapper != NULL ? wrapper : PyErr_NoMemory ();
}

static PyObject *
weakref_unref (GinextGObjectWeakRef *self, PyObject *args G_GNUC_UNUSED)
{
  if (self->cancelled)
    {
      PyErr_SetString (PyExc_ValueError, "GObjectWeakRef already unreffed");
      return NULL;
    }
  self->cancelled = 1;
  if (self->object != NULL)
    {
      g_object_weak_unref (self->object, weakref_notify, self);
      /* weakref_notify won't fire so drop the self-ref it would have dropped. */
      Py_DECREF (self);
    }
  Py_RETURN_NONE;
}

static PyMethodDef weakref_methods[] = {
  { "unref", (PyCFunction)weakref_unref, METH_NOARGS, NULL },
  { NULL }
};

PyType_Slot GinextGObjectWeakRef_slots[] = {
  { Py_tp_dealloc, weakref_dealloc },
  { Py_tp_call, weakref_call },
  { Py_tp_methods, weakref_methods },
  { 0, NULL }
};

PyType_Spec GinextGObjectWeakRef_spec = {
  .name = "ginext._gobject.GObjectWeakRef",
  .basicsize = sizeof (GinextGObjectWeakRef),
  .flags = Py_TPFLAGS_DEFAULT,
  .slots = GinextGObjectWeakRef_slots,
};

static PyTypeObject *GinextGObjectWeakRef_type = NULL;

PyObject *
py_gobject_add_weak_notify (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *wrapper;
  PyObject *callback;
  PyObject *cb_args;
  if (!PyArg_ParseTuple (args, "OOO!", &wrapper, &callback, &PyTuple_Type, &cb_args))
    return NULL;

  if (!PyCallable_Check (callback))
    {
      PyErr_SetString (PyExc_TypeError, "weak_ref callback must be callable");
      return NULL;
    }

  GObject *object = pygi_gobject_get (wrapper);
  if (object == NULL)
    return NULL;

  if (GinextGObjectWeakRef_type == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "GObjectWeakRef type not initialised");
      return NULL;
    }

  GinextGObjectWeakRef *wr =
    PyObject_New (GinextGObjectWeakRef, GinextGObjectWeakRef_type);
  if (wr == NULL)
    return NULL;

  wr->object = object;
  wr->callback = Py_NewRef (callback);
  wr->args = Py_NewRef (cb_args);
  wr->cancelled = 0;

  /* Take an extra self-reference so the notify callback can Py_DECREF(self)
   * without needing the caller to keep their handle alive. */
  Py_INCREF (wr);
  g_object_weak_ref (object, weakref_notify, wr);

  return (PyObject *)wr;
}

int
pygi_gobject_weakref_init (PyObject *module)
{
  PyObject *type = PyType_FromModuleAndSpec (module, &GinextGObjectWeakRef_spec, NULL);
  if (type == NULL)
    return -1;
  GinextGObjectWeakRef_type = (PyTypeObject *)type;
  if (PyModule_AddObject (module, "GObjectWeakRef", type) < 0)
    {
      Py_DECREF (type);
      GinextGObjectWeakRef_type = NULL;
      return -1;
    }
  return 0;
}
