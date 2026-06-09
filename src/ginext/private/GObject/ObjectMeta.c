/* Copyright 2026 Johan Dahlin
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 *
 * GObjectMeta — the metaclass shared by every ginext GObject class, in C.
 *
 * Its only load-bearing job is class-level attribute access: a custom
 * tp_getattro so `SomeClass.introspected_method` lazily builds and installs the
 * method on first access (instance access goes through GObject.Object's own
 * tp_getattro, not here). The behaviour stays in Python — this is just the
 * metatype structure plus two slots that delegate to registered hooks. */

#include "common.h"
#include "GObject/ObjectMeta.h"

/* Python bodies the slots delegate to, registered at bootstrap. */
static PyObject *meta_cb_getattr = NULL;
static PyObject *meta_cb_dir = NULL;

void
pygi_gobjectmeta_set_hooks (PyObject *meta_getattr, PyObject *meta_dir)
{
  if (meta_getattr != NULL)
    Py_XSETREF (meta_cb_getattr, Py_NewRef (meta_getattr));
  if (meta_dir != NULL)
    Py_XSETREF (meta_cb_dir, Py_NewRef (meta_dir));
}

/* tp_getattro: normal class-attribute lookup, then the registered class-level
 * __getattr__ body (lazy introspected-method install) on a genuine miss. */
static PyObject *
gobjectmeta_getattro (PyObject *cls, PyObject *name)
{
  PyObject *result = PyType_Type.tp_getattro (cls, name);
  if (result != NULL || !PyErr_ExceptionMatches (PyExc_AttributeError))
    return result;
  if (meta_cb_getattr == NULL)
    return NULL; /* keep the AttributeError */
  PyErr_Clear ();
  return PyObject_CallFunctionObjArgs (meta_cb_getattr, cls, name, NULL);
}

/* __dir__: delegate to the registered body (which augments type.__dir__ with the
 * lazily-installable introspected methods). Falls back to type.__dir__ before
 * the hook is registered. */
static PyObject *
gobjectmeta_dir (PyObject *cls, PyObject *Py_UNUSED (ignored))
{
  if (meta_cb_dir != NULL)
    return PyObject_CallFunctionObjArgs (meta_cb_dir, cls, NULL);
  PyObject *type_dir = PyObject_GetAttrString ((PyObject *)&PyType_Type, "__dir__");
  if (type_dir == NULL)
    return NULL;
  PyObject *result = PyObject_CallFunctionObjArgs (type_dir, cls, NULL);
  Py_DECREF (type_dir);
  return result;
}

static PyMethodDef gobjectmeta_methods[] = {
  { "__dir__", (PyCFunction)gobjectmeta_dir, METH_NOARGS, NULL },
  { NULL, NULL, 0, NULL },
};

static PyType_Slot gobjectmeta_slots[] = {
  { Py_tp_getattro, gobjectmeta_getattro },
  { Py_tp_methods, gobjectmeta_methods },
  { 0, NULL },
};

static PyType_Spec gobjectmeta_spec = {
  .name = "ginext.private._gobject.GObjectMeta",
  .basicsize = 0,
  .itemsize = 0,
  .flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .slots = gobjectmeta_slots,
};

PyObject *
pygi_create_gobjectmeta (PyObject *module)
{
  PyObject *bases = PyTuple_Pack (1, (PyObject *)&PyType_Type);
  if (bases == NULL)
    return NULL;
  PyObject *meta = PyType_FromMetaclass (NULL, module, &gobjectmeta_spec, bases);
  Py_DECREF (bases);
  if (meta == NULL)
    return NULL;
  if (PyModule_AddObjectRef (module, "GObjectMeta", meta) < 0)
    {
      Py_DECREF (meta);
      return NULL;
    }
  return meta;
}
