/* Copyright 2026 Johan Dahlin
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 */

/* Expose native GIR vfuncs as `Class.do_<name>` callables for chain-up.
 *
 * Python overrides use these in the PyGObject style:
 *     class App(Gtk.Application):
 *         def do_startup(self):
 *             Gtk.Application.do_startup(self)
 *
 * The wrapper invokes the vfunc through the GType that supplied the
 * descriptor, so calling the parent class dispatches the parent slot instead
 * of recursing into the subclass override.
 */
#include "GObject/Object-vfunc-wrapper.h"
#include "gimeta-helpers.h"

#include <girepository/girepository.h>
#include <string.h>

#include "GIRepository/BaseInfo.h"
#include "GObject/Boxed.h"
#include "GObject/Object.h"
#include "marshal/marshal.h"

PyTypeObject *ginext_vfunc_wrapper_type = NULL;

typedef struct
{
  PyObject_HEAD GIVFuncInfo *vfunc_info;
  GType implementor;
} GinextVFuncWrapper;

static void
VFuncWrapper_dealloc (PyObject *self)
{
  GinextVFuncWrapper *w = (GinextVFuncWrapper *)self;
  if (w->vfunc_info != NULL)
    gi_base_info_unref ((GIBaseInfo *)w->vfunc_info);
  Py_TYPE (self)->tp_free (self);
}

static int
class_gtype (PyObject *cls, GType *out)
{
  return pygi_gtype_from_py_object (cls, out);
}

static int
py_to_giarg (PyObject *obj, GIArgument *out)
{
  if (obj == Py_None)
    {
      out->v_pointer = NULL;
      return 0;
    }
  if (PyBool_Check (obj))
    {
      out->v_boolean = obj == Py_True;
      return 0;
    }
  if (PyLong_Check (obj))
    {
      out->v_long = PyLong_AsLong (obj);
      return PyErr_Occurred () ? -1 : 0;
    }

  GObject *gobj = pygi_gobject_get (obj);
  if (gobj != NULL)
    {
      PyErr_Clear ();
      out->v_pointer = gobj;
      return 0;
    }
  PyErr_Clear ();

  gpointer boxed = NULL;
  if (pygi_boxed_get (obj, &boxed) == 0)
    {
      PyErr_Clear ();
      out->v_pointer = boxed;
      return 0;
    }
  PyErr_Clear ();

  PyErr_Format (PyExc_TypeError,
                "vfunc chain-up: don't know how to marshal %s",
                Py_TYPE (obj)->tp_name);
  return -1;
}

/* A transfer-full parameter is consumed (unref/free) by the callee. py_to_giarg
 * hands over the raw pointer the Python wrapper still owns, so without an extra
 * ref/copy the wrapper's later free becomes a double free. Mirror the regular
 * method-call path (boxed_transfer_full_arg_from_py / the GObject ref in
 * marshal.c) for vfunc chain-up. */
static int
vfunc_ref_transfer_full_arg (PyObject *obj, GIArgInfo *ainfo, GIArgument *arg)
{
  if (arg->v_pointer == NULL)
    return 0;
  GObject *gobj = pygi_gobject_get (obj);
  if (gobj != NULL)
    {
      g_object_ref (gobj);
      return 0;
    }
  PyErr_Clear ();
  gpointer boxed = NULL;
  if (pygi_boxed_get (obj, &boxed) == 0 && boxed != NULL)
    {
      g_autoptr (GITypeInfo) ti = gi_arg_info_get_type_info (ainfo);
      g_autoptr (GIBaseInfo) iface = ti != NULL ? gi_type_info_get_interface (ti) : NULL;
      if (iface != NULL)
        {
          GType gt = gi_registered_type_info_get_g_type ((GIRegisteredTypeInfo *)iface);
          if (gt != G_TYPE_NONE && gt != 0 && G_TYPE_IS_BOXED (gt))
            arg->v_pointer = g_boxed_copy (gt, boxed);
        }
      return 0;
    }
  PyErr_Clear ();
  return 0;
}

static PyObject *
VFuncWrapper_call (PyObject *self, PyObject *args, PyObject *kw)
{
  GinextVFuncWrapper *w = (GinextVFuncWrapper *)self;
  if (kw != NULL && PyDict_GET_SIZE (kw) != 0)
    {
      PyErr_SetString (PyExc_TypeError, "vfunc chain-up doesn't accept keyword arguments");
      return NULL;
    }

  Py_ssize_t n_py = PyTuple_GET_SIZE (args);
  if (n_py == 0)
    {
      PyErr_SetString (PyExc_TypeError, "vfunc chain-up requires self as the first argument");
      return NULL;
    }

  GICallableInfo *cinfo = (GICallableInfo *)w->vfunc_info;
  guint n_vfunc_args = gi_callable_info_get_n_args (cinfo);
  GIArgument *in_args = g_alloca (sizeof (GIArgument) * (gsize)n_py);
  for (Py_ssize_t i = 0; i < n_py; i++)
    {
      PyObject *item = PyTuple_GET_ITEM (args, i);
      memset (&in_args[i], 0, sizeof (GIArgument));
      if (py_to_giarg (item, &in_args[i]) != 0)
        return NULL;
      /* in_args[0] is the instance; vfunc parameters start at in_args[1]. */
      if (i >= 1 && (guint)(i - 1) < n_vfunc_args)
        {
          g_autoptr (GIArgInfo) ainfo = gi_callable_info_get_arg (cinfo, (guint)(i - 1));
          if (ainfo != NULL
              && gi_arg_info_get_ownership_transfer (ainfo) == GI_TRANSFER_EVERYTHING
              && vfunc_ref_transfer_full_arg (item, ainfo, &in_args[i]) != 0)
            return NULL;
        }
    }

  GIArgument retval = { 0 };
  g_autoptr (GError) error = NULL;
  if (!gi_vfunc_info_invoke (w->vfunc_info,
                             w->implementor,
                             in_args,
                             (size_t)n_py,
                             NULL,
                             0,
                             &retval,
                             &error))
    {
      PyErr_Format (PyExc_RuntimeError,
                    "vfunc chain-up failed: %s",
                    error != NULL ? error->message : "unknown");
      return NULL;
    }

  g_autoptr (GITypeInfo) ret_ti
      = gi_callable_info_get_return_type ((GICallableInfo *)w->vfunc_info);
  if (ret_ti == NULL || gi_type_info_get_tag (ret_ti) == GI_TYPE_TAG_VOID)
    Py_RETURN_NONE;

  GITransfer transfer = gi_callable_info_get_caller_owns ((GICallableInfo *)w->vfunc_info);
  return pygi_argument_to_py_transfer ((GICallableInfo *)w->vfunc_info, ret_ti, &retval, transfer);
}

static PyObject *
VFuncWrapper_repr (PyObject *self)
{
  GinextVFuncWrapper *w = (GinextVFuncWrapper *)self;
  const char *vname
      = w->vfunc_info != NULL ? gi_base_info_get_name ((GIBaseInfo *)w->vfunc_info) : "(unbound)";
  return PyUnicode_FromFormat ("<vfunc '%s' on %s>", vname, g_type_name (w->implementor));
}

static PyObject *
VFuncWrapper_descr_get (PyObject *self, PyObject *obj, PyObject *type)
{
  GinextVFuncWrapper *w = (GinextVFuncWrapper *)self;

  if (obj != NULL)
    return PyMethod_New (self, obj);
  if (type == NULL || !PyType_Check (type))
    return Py_NewRef (self);

  GType bound_gt = w->implementor;
  if (class_gtype (type, &bound_gt) != 0)
    PyErr_Clear ();

  if (bound_gt == w->implementor)
    return Py_NewRef (self);

  PyObject *bound = PyType_GenericAlloc (ginext_vfunc_wrapper_type, 0);
  if (bound == NULL)
    return NULL;
  GinextVFuncWrapper *b = (GinextVFuncWrapper *)bound;
  b->vfunc_info = (GIVFuncInfo *)gi_base_info_ref ((GIBaseInfo *)w->vfunc_info);
  b->implementor = bound_gt;
  return bound;
}

static PyType_Slot VFuncWrapper_slots[] = {
  { Py_tp_dealloc, (void *)VFuncWrapper_dealloc },
  { Py_tp_call, (void *)VFuncWrapper_call },
  { Py_tp_repr, (void *)VFuncWrapper_repr },
  { Py_tp_descr_get, (void *)VFuncWrapper_descr_get },
  { 0, NULL },
};

PyType_Spec GinextVFuncWrapper_spec = {
  .name = "ginext.private._gobject.VFuncWrapper",
  .basicsize = sizeof (GinextVFuncWrapper),
  .flags = Py_TPFLAGS_DEFAULT,
  .slots = VFuncWrapper_slots,
};

PyObject *
py_install_native_vfunc_attrs (PyObject *module G_GNUC_UNUSED, PyObject *args)
{
  PyObject *cls = NULL;
  PyObject *capsule = NULL;
  if (!PyArg_ParseTuple (args, "OO", &cls, &capsule))
    return NULL;
  if (pygi_install_native_vfunc_attrs_for_class (cls, capsule) < 0)
    return NULL;
  Py_RETURN_NONE;
}

int
pygi_install_native_vfunc_attrs_for_class (PyObject *cls, PyObject *capsule)
{
  if (ginext_vfunc_wrapper_type == NULL)
    return 0;

  GIBaseInfo *base = gi_info_from_py (capsule);
  if (base == NULL)
    return -1;
  if (!GI_IS_OBJECT_INFO (base))
    return 0;

  GType implementor = 0;
  if (class_gtype (cls, &implementor) != 0)
    return -1;

  GIObjectInfo *oinfo = (GIObjectInfo *)base;
  unsigned int n_vfuncs = gi_object_info_get_n_vfuncs (oinfo);
  for (unsigned int i = 0; i < n_vfuncs; i++)
    {
      g_autoptr (GIVFuncInfo) vfunc = gi_object_info_get_vfunc (oinfo, i);
      if (vfunc == NULL)
        continue;
      const char *vname = gi_base_info_get_name ((GIBaseInfo *)vfunc);
      if (vname == NULL)
        continue;

      g_autofree char *attr = g_strconcat ("do_", vname, NULL);
      if (PyType_Check (cls) && PyDict_GetItemString (((PyTypeObject *)cls)->tp_dict, attr) != NULL)
        continue;

      PyObject *wrapper = PyType_GenericAlloc (ginext_vfunc_wrapper_type, 0);
      if (wrapper == NULL)
        return -1;
      GinextVFuncWrapper *w = (GinextVFuncWrapper *)wrapper;
      w->vfunc_info = (GIVFuncInfo *)gi_base_info_ref ((GIBaseInfo *)vfunc);
      w->implementor = implementor;

      if (PyObject_SetAttrString (cls, attr, wrapper) < 0)
        {
          Py_DECREF (wrapper);
          return -1;
        }
      Py_DECREF (wrapper);
    }

  return 0;
}
