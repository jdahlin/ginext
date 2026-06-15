#include "property-descr.h"

#include "GIMeta.h"
#include "Object-info.h"
#include "ParamSpec.h"
#include "marshal/gvalue.h"

typedef struct
{
  PyObject_HEAD PyObject *spec;
  PyObject *name;
  PyObject *owner;
  GParamSpec *pspec;
  GType owner_type;
  gint private_offset;
  guint prop_id;
  int coerce_gtype_int;
} GinextPropertyDescriptor;

static inline InstancePrivate *
declared_property_private_from_instance (GinextPropertyDescriptor *self, GTypeInstance *instance)
{
  if (G_UNLIKELY (self->owner_type == 0))
    self->owner_type = self->pspec->owner_type;
  if (G_UNLIKELY (self->private_offset < 0))
    {
      ClassState *state = class_state_from_type (self->owner_type);
      self->private_offset = state ? state->private_offset : -1;
    }
  return (InstancePrivate *)G_STRUCT_MEMBER_P (instance, self->private_offset);
}

static GObject *
gobject_from_py (PyObject *py_obj)
{
  GObject *obj = pygi_gobject_get (py_obj);
  if (!obj)
    return NULL;
  if (!obj && !PyErr_Occurred ())
    PyErr_SetString (PyExc_ValueError, "GObject pointer is NULL");
  return obj;
}

static int
call_notify_override (GinextPropertyDescriptor *self, PyObject *obj)
{
  PyObject *obj_type = (PyObject *)Py_TYPE (obj);
  PyObject *dict = ((PyTypeObject *)obj_type)->tp_dict;
  PyObject *overrides = PyDict_GetItemString (dict, "_pygobject_signal_overrides");
  if (!overrides || !PySet_Check (overrides))
    return 0;

  PyObject *notify = PyUnicode_FromString ("notify");
  if (!notify)
    return -1;
  int has_notify = PySet_Contains (overrides, notify);
  Py_DECREF (notify);
  if (has_notify <= 0)
    return has_notify;

  Py_AUTO_DECREF PyObject *default_handler = PyObject_GetAttrString (obj, "do_notify");
  if (!default_handler)
    {
      if (PyErr_ExceptionMatches (PyExc_AttributeError))
        {
          PyErr_Clear ();
          return 0;
        }
      return -1;
    }
  if (!PyCallable_Check (default_handler))
    return 0;

  Py_AUTO_DECREF PyObject *pspec = pygi_param_spec_new (self->pspec);
  if (!pspec)
    return -1;

  PyObject *result = PyObject_CallFunctionObjArgs (default_handler, pspec, NULL);
  if (!result)
    return -1;
  Py_DECREF (result);
  return 0;
}

static void
declared_property_dealloc (GinextPropertyDescriptor *self)
{
  Py_XDECREF (self->spec);
  Py_XDECREF (self->name);
  Py_XDECREF (self->owner);
  if (self->pspec)
    g_param_spec_unref (self->pspec);
  Py_TYPE (self)->tp_free ((PyObject *)self);
}

static PyObject *
declared_property_repr (GinextPropertyDescriptor *self)
{
  return PyUnicode_FromFormat ("<ginext.DeclaredProperty %R>", self->name);
}

static PyObject *
declared_property_descr_get (PyObject *descr, PyObject *obj, PyObject *objtype G_GNUC_UNUSED)
{
  GinextPropertyDescriptor *self = (GinextPropertyDescriptor *)descr;
  if (obj == NULL || obj == Py_None)
    return Py_NewRef (descr);

  GObject *g_obj = gobject_from_py (obj);
  if (!g_obj)
    return NULL;

  if (!(self->pspec->flags & G_PARAM_READABLE))
    {
      PyErr_Format (PyExc_AttributeError,
                    "property %U on %s is not readable",
                    self->name,
                    Py_TYPE (obj)->tp_name);
      return NULL;
    }

  InstancePrivate *priv = declared_property_private_from_instance (self, (GTypeInstance *)g_obj);
  Py_AUTO_DECREF PyObject *value = pygi_gvalue_value_to_py (&priv->props[self->prop_id - 1]);
  if (!value)
    return NULL;
  if (!self->coerce_gtype_int)
    return Py_NewRef (value);
  return PyNumber_Long (value);
}

static int
declared_property_descr_set (PyObject *descr, PyObject *obj, PyObject *value)
{
  GinextPropertyDescriptor *self = (GinextPropertyDescriptor *)descr;
  if (value == NULL)
    {
      PyErr_Format (PyExc_AttributeError, "cannot delete property %U", self->name);
      return -1;
    }

  if (!(self->pspec->flags & G_PARAM_WRITABLE))
    {
      PyErr_Format (PyExc_AttributeError,
                    "property %U on %s is read-only",
                    self->name,
                    Py_TYPE (obj)->tp_name);
      return -1;
    }
  if (self->pspec->flags & G_PARAM_CONSTRUCT_ONLY)
    {
      PyErr_Format (PyExc_AttributeError,
                    "property %U on %s is construct-only",
                    self->name,
                    Py_TYPE (obj)->tp_name);
      return -1;
    }

  GObject *g_obj = gobject_from_py (obj);
  if (!g_obj)
    return -1;

  InstancePrivate *priv = declared_property_private_from_instance (self, (GTypeInstance *)g_obj);
  if (pygi_py_to_gvalue_property (value, &priv->props[self->prop_id - 1]) < 0)
    return -1;

  g_object_notify_by_pspec (g_obj, self->pspec);
  if (call_notify_override (self, obj) < 0)
    return -1;
  return 0;
}

static PyObject *
declared_property_getattro (PyObject *obj, PyObject *name)
{
  PyObject *result = PyObject_GenericGetAttr (obj, name);
  if (result || !PyErr_ExceptionMatches (PyExc_AttributeError))
    return result;

  PyErr_Clear ();
  GinextPropertyDescriptor *self = (GinextPropertyDescriptor *)obj;
  return PyObject_GetAttr (self->spec, name);
}

static PyObject *
declared_property_get_pspec (GinextPropertyDescriptor *self, void *closure G_GNUC_UNUSED)
{
  return pygi_param_spec_new (self->pspec);
}

static PyObject *
declared_property_get_owner (GinextPropertyDescriptor *self, void *closure G_GNUC_UNUSED)
{
  return Py_NewRef (self->owner);
}

static PyObject *
declared_property_get_name (GinextPropertyDescriptor *self, void *closure G_GNUC_UNUSED)
{
  return Py_NewRef (self->name);
}

static PyGetSetDef declared_property_getsets[]
    = { { "pspec", (getter)declared_property_get_pspec, NULL, NULL, NULL },
        { "owner", (getter)declared_property_get_owner, NULL, NULL, NULL },
        { "name", (getter)declared_property_get_name, NULL, NULL, NULL },
        { 0 } };

PyObject *
pygi_declared_property_new_full (PyObject *spec,
                                 PyObject *owner,
                                 PyObject *prop_id_obj,
                                 PyObject *pspec_obj,
                                 int coerce_gtype_int)
{
  Py_AUTO_DECREF PyObject *name = PyObject_GetAttrString (spec, "name");
  if (!name)
    return NULL;
  long prop_id = PyLong_AsLong (prop_id_obj);
  if (prop_id == -1 && PyErr_Occurred ())
    return NULL;
  if (prop_id <= 0)
    {
      PyErr_SetString (PyExc_ValueError, "prop_id must be positive");
      return NULL;
    }
  GParamSpec *pspec = (GParamSpec *)PyLong_AsVoidPtr (pspec_obj);
  if (!pspec && PyErr_Occurred ())
    return NULL;
  if (!pspec)
    {
      PyErr_SetString (PyExc_ValueError, "pspec must not be NULL");
      return NULL;
    }

  GinextPropertyDescriptor *self = PyObject_New (GinextPropertyDescriptor, &GinextPropertyDescriptorType);
  if (!self)
    return NULL;
  self->spec = Py_NewRef (spec);
  self->name = Py_NewRef (name);
  self->owner = Py_NewRef (owner);
  self->pspec = g_param_spec_ref (pspec);
  self->owner_type = 0;
  self->private_offset = -1;
  self->prop_id = (guint)prop_id;
  self->coerce_gtype_int = coerce_gtype_int;
  return (PyObject *)self;
}

static PyObject *
declared_property_from_spec (PyTypeObject *cls G_GNUC_UNUSED, PyObject *args)
{
  PyObject *spec = NULL;
  PyObject *owner = NULL;
  PyObject *prop_id_obj = NULL;
  PyObject *pspec_obj = NULL;
  int coerce_gtype_int = 0;
  if (!PyArg_ParseTuple (args,
                         "OOOO|p:from_spec",
                         &spec,
                         &owner,
                         &prop_id_obj,
                         &pspec_obj,
                         &coerce_gtype_int))
    return NULL;
  return pygi_declared_property_new_full (spec, owner, prop_id_obj, pspec_obj, coerce_gtype_int);
}

static PyMethodDef declared_property_methods[]
    = { { "from_spec", (PyCFunction)declared_property_from_spec, METH_VARARGS | METH_CLASS, NULL },
        { NULL } };

PyTypeObject GinextPropertyDescriptorType = {
  PyVarObject_HEAD_INIT (NULL, 0).tp_name = "ginext.private.PropertyDescriptor",
  .tp_basicsize = sizeof (GinextPropertyDescriptor),
  .tp_dealloc = (destructor)declared_property_dealloc,
  .tp_repr = (reprfunc)declared_property_repr,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_descr_get = declared_property_descr_get,
  .tp_descr_set = declared_property_descr_set,
  .tp_methods = declared_property_methods,
  .tp_getset = declared_property_getsets,
  .tp_getattro = declared_property_getattro,
};
