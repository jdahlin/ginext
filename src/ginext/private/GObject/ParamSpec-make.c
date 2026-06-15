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

/* Build a GParamSpec from a Python `Property` descriptor + annotation type.
 *
 * The annotation drives the value_type (`bool` → G_TYPE_BOOLEAN, etc.).
 * GObject-class annotations resolve via `cls.gimeta.gtype`. The dispatch
 * switches on G_TYPE_FUNDAMENTAL so e.g. every subclass of GObject lands
 * in the G_TYPE_OBJECT branch.
 *
 * `RANGE_CHECK_S/U` guard against Python int defaults that exceed the
 * target C type's range (PyLong_AsLongLong only catches >64-bit overflow,
 * so gint/gchar/etc. need their own narrower checks). `CHECK_PSPEC`
 * turns a NULL return from g_param_spec_* into a Python ValueError —
 * GLib's runtime checks (default outside [min,max], etc.) only log a
 * critical without setting a Python error.
 */
#include "ParamSpec-make.h"

#include "GObject/Boxed.h"
#include "GLib/Variant.h"
#include "gimeta-helpers.h"

#include <math.h>

static gboolean
is_unset_sentinel (PyObject *obj)
{
  /* ginext.gobject._unset is `object()`. Detect by exact type. */
  return Py_TYPE (obj) == &PyBaseObject_Type;
}

/* Map a Python annotation to a GType. Returns G_TYPE_INVALID when the
 * annotation isn't dispatchable and (separately) sets a Python error
 * only on genuine failure (attribute lookup raised). */
static GType
gtype_from_value_type (PyObject *value_type)
{
  if (value_type == (PyObject *)&PyBool_Type)
    return G_TYPE_BOOLEAN;
  if (value_type == (PyObject *)&PyLong_Type)
    return G_TYPE_INT64;
  if (value_type == (PyObject *)&PyFloat_Type)
    return G_TYPE_DOUBLE;
  if (value_type == (PyObject *)&PyUnicode_Type)
    return G_TYPE_STRING;
  if (value_type == (PyObject *)&PyBytes_Type)
    return G_TYPE_STRING;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (value_type, &gtype) != 0)
    {
      PyErr_Clear ();
      return G_TYPE_INVALID;
    }
  return gtype;
}

static int
check_signed_range (long long value,
                    long long lo,
                    long long hi,
                    const char *label,
                    const char *attr_name)
{
  if (value < lo || value > hi)
    {
      PyErr_Format (PyExc_OverflowError,
                    "%s %lld out of range [%lld, %lld] for %s",
                    label,
                    value,
                    lo,
                    hi,
                    attr_name);
      return -1;
    }
  return 0;
}

static int
check_unsigned_range (unsigned long long value,
                      unsigned long long hi,
                      const char *label,
                      const char *attr_name)
{
  if (value > hi)
    {
      PyErr_Format (PyExc_OverflowError,
                    "%s %llu out of range [0, %llu] for %s",
                    label,
                    value,
                    hi,
                    attr_name);
      return -1;
    }
  return 0;
}

static int
check_float_range (double value, double lo, double hi, const char *label, const char *attr_name)
{
  if (!isfinite (value) || value < lo || value > hi)
    {
      PyErr_Format (PyExc_ValueError, "%s out of range for %s", label, attr_name);
      return -1;
    }
  return 0;
}

static int
check_signed_bounds (long long minimum, long long maximum, const char *attr_name)
{
  if (minimum > maximum)
    {
      PyErr_Format (PyExc_ValueError,
                    "minimum %lld greater than maximum %lld for %s",
                    minimum,
                    maximum,
                    attr_name);
      return -1;
    }
  return 0;
}

static int
check_unsigned_bounds (unsigned long long minimum,
                       unsigned long long maximum,
                       const char *attr_name)
{
  if (minimum > maximum)
    {
      PyErr_Format (PyExc_ValueError,
                    "minimum %llu greater than maximum %llu for %s",
                    minimum,
                    maximum,
                    attr_name);
      return -1;
    }
  return 0;
}

static int
check_float_bounds (double minimum, double maximum, const char *attr_name)
{
  if (!isfinite (minimum) || !isfinite (maximum) || minimum > maximum)
    {
      PyErr_Format (PyExc_ValueError, "invalid minimum/maximum for %s", attr_name);
      return -1;
    }
  return 0;
}

GParamSpec *
make_pspec (const char *attr_name, PyObject *value_type, PyObject *prop)
{
  if (!*attr_name)
    {
      PyErr_SetString (PyExc_ValueError, "property name cannot be empty");
      return NULL;
    }

  Py_AUTO_DECREF PyObject *nick_o = NULL;
  Py_AUTO_DECREF PyObject *blurb_o = NULL;
  Py_AUTO_DECREF PyObject *default_o = NULL;
  Py_AUTO_DECREF PyObject *minimum_o = NULL;
  Py_AUTO_DECREF PyObject *maximum_o = NULL;
  if (PyObject_GetOptionalAttrString (prop, "nick", &nick_o) < 0
      || PyObject_GetOptionalAttrString (prop, "blurb", &blurb_o) < 0
      || PyObject_GetOptionalAttrString (prop, "default", &default_o) < 0
      || PyObject_GetOptionalAttrString (prop, "minimum", &minimum_o) < 0
      || PyObject_GetOptionalAttrString (prop, "maximum", &maximum_o) < 0)
    return NULL;

  const char *nick = (nick_o && !Py_IsNone (nick_o)) ? PyUnicode_AsUTF8 (nick_o) : NULL;
  const char *blurb = (blurb_o && !Py_IsNone (blurb_o)) ? PyUnicode_AsUTF8 (blurb_o) : NULL;
  if (PyErr_Occurred ())
    return NULL;

  gboolean has_default = default_o && !Py_IsNone (default_o) && !is_unset_sentinel (default_o);
  gboolean has_minimum = minimum_o && !Py_IsNone (minimum_o);
  gboolean has_maximum = maximum_o && !Py_IsNone (maximum_o);

  Py_AUTO_DECREF PyObject *readonly_o = NULL;
  Py_AUTO_DECREF PyObject *construct_o = NULL;
  if (PyObject_GetOptionalAttrString (prop, "readonly", &readonly_o) < 0
      || PyObject_GetOptionalAttrString (prop, "construct_only", &construct_o) < 0)
    return NULL;
  int readonly = readonly_o ? PyObject_IsTrue (readonly_o) : 0;
  int construct = construct_o ? PyObject_IsTrue (construct_o) : 0;
  if (readonly < 0 || construct < 0)
    return NULL;

  GParamFlags flags = readonly ? G_PARAM_READABLE : G_PARAM_READWRITE;
  if (construct)
    {
      /* GLib requires CONSTRUCT_ONLY params to remain writable during
       * construction, even if the Python descriptor should reject writes
       * afterwards. */
      flags |= G_PARAM_WRITABLE | G_PARAM_CONSTRUCT_ONLY;
    }

  GType gtype = gtype_from_value_type (value_type);
  if (PyErr_Occurred ())
    return NULL;

  /* G_TYPE_GTYPE is a function call (g_gtype_get_type()), not a compile-
     * time constant — handle before the switch on fundamental types. */
  if (gtype == G_TYPE_GTYPE)
    {
      GType default_gtype = G_TYPE_NONE;
      if (has_default)
        {
          if (pygi_gtype_from_py_object (default_o, &default_gtype) != 0)
            return NULL;
        }
      return g_param_spec_gtype (attr_name, nick, blurb, default_gtype, flags);
    }
  if (gtype == G_TYPE_VARIANT)
    {
      g_autoptr (GVariant) default_variant = NULL;
      if (has_default)
        {
          if (!(PyObject_TypeCheck (default_o, pygi_gboxed_base_type)
                && ((PyGIGLibBoxed *)default_o)->gtype == G_TYPE_VARIANT))
            {
              PyErr_SetString (PyExc_TypeError, "GVariant property default must be GLib.Variant");
              return NULL;
            }
          void *variant = NULL;
          if (pygi_py_item_to_gvariant (default_o, &variant) != 0)
            return NULL;
          default_variant = (GVariant *)variant;
        }
      const GVariantType *variant_type = G_VARIANT_TYPE_ANY;
      GParamSpec *pspec
          = g_param_spec_variant (attr_name, nick, blurb, variant_type, default_variant, flags);
      if (!pspec && !PyErr_Occurred ())
        PyErr_Format (PyExc_ValueError,
                      "GLib rejected the pspec for %s - likely an "
                      "out-of-range or invalid default",
                      attr_name);
      return pspec;
    }

#define DEFAULT_LONG(zero) (has_default ? PyLong_AsLongLong (default_o) : (zero))
#define DEFAULT_ULONG(zero) (has_default ? PyLong_AsUnsignedLongLong (default_o) : (zero))
#define DEFAULT_FLOAT(zero) (has_default ? PyFloat_AsDouble (default_o) : (zero))
#define MIN_LONG(zero) (has_minimum ? PyLong_AsLongLong (minimum_o) : (zero))
#define MAX_LONG(zero) (has_maximum ? PyLong_AsLongLong (maximum_o) : (zero))
#define MIN_ULONG(zero) (has_minimum ? PyLong_AsUnsignedLongLong (minimum_o) : (zero))
#define MAX_ULONG(zero) (has_maximum ? PyLong_AsUnsignedLongLong (maximum_o) : (zero))
#define MIN_FLOAT(zero) (has_minimum ? PyFloat_AsDouble (minimum_o) : (zero))
#define MAX_FLOAT(zero) (has_maximum ? PyFloat_AsDouble (maximum_o) : (zero))
#define CHECK_CONV()                                                                               \
  do                                                                                               \
    {                                                                                              \
      if (PyErr_Occurred ())                                                                       \
        return NULL;                                                                               \
    }                                                                                              \
  while (0)
#define CHECK_PSPEC(p)                                                                             \
  do                                                                                               \
    {                                                                                              \
      GParamSpec *_p = (p);                                                                        \
      if (!_p && !PyErr_Occurred ())                                                               \
        PyErr_Format (PyExc_ValueError,                                                            \
                      "GLib rejected the pspec for %s - likely an "                                \
                      "out-of-range or invalid default",                                           \
                      attr_name);                                                                  \
      return _p;                                                                                   \
    }                                                                                              \
  while (0)

  switch (G_TYPE_FUNDAMENTAL (gtype))
    {
    case G_TYPE_BOOLEAN:
      {
        int d = has_default ? PyObject_IsTrue (default_o) : 0;
        if (d < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_boolean (attr_name, nick, blurb, (gboolean)d, flags));
      }
    case G_TYPE_CHAR:
      {
        long long minimum = MIN_LONG (G_MININT8);
        long long maximum = MAX_LONG (G_MAXINT8);
        long long d = DEFAULT_LONG (0);
        CHECK_CONV ();
        if (check_signed_range (minimum, G_MININT8, G_MAXINT8, "minimum", attr_name) < 0
            || check_signed_range (maximum, G_MININT8, G_MAXINT8, "maximum", attr_name) < 0
            || check_signed_bounds (minimum, maximum, attr_name) < 0
            || check_signed_range (d, minimum, maximum, "default", attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_char (attr_name,
                                        nick,
                                        blurb,
                                        (gint8)minimum,
                                        (gint8)maximum,
                                        (gint8)d,
                                        flags));
      }
    case G_TYPE_UCHAR:
      {
        unsigned long long minimum = MIN_ULONG (0);
        unsigned long long maximum = MAX_ULONG (G_MAXUINT8);
        unsigned long long d = DEFAULT_ULONG (0);
        CHECK_CONV ();
        if (check_unsigned_range (minimum, G_MAXUINT8, "minimum", attr_name) < 0
            || check_unsigned_range (maximum, G_MAXUINT8, "maximum", attr_name) < 0
            || check_unsigned_bounds (minimum, maximum, attr_name) < 0
            || check_unsigned_range (d, maximum, "default", attr_name) < 0
            || check_unsigned_bounds (minimum, d, attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_uchar (attr_name,
                                         nick,
                                         blurb,
                                         (guint8)minimum,
                                         (guint8)maximum,
                                         (guint8)d,
                                         flags));
      }
    case G_TYPE_INT:
      {
        long long minimum = MIN_LONG (G_MININT);
        long long maximum = MAX_LONG (G_MAXINT);
        long long d = DEFAULT_LONG (0);
        CHECK_CONV ();
        if (check_signed_range (minimum, G_MININT, G_MAXINT, "minimum", attr_name) < 0
            || check_signed_range (maximum, G_MININT, G_MAXINT, "maximum", attr_name) < 0
            || check_signed_bounds (minimum, maximum, attr_name) < 0
            || check_signed_range (d, minimum, maximum, "default", attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_int (attr_name,
                                       nick,
                                       blurb,
                                       (gint)minimum,
                                       (gint)maximum,
                                       (gint)d,
                                       flags));
      }
    case G_TYPE_UINT:
      {
        unsigned long long minimum = MIN_ULONG (0);
        unsigned long long maximum = MAX_ULONG (G_MAXUINT);
        unsigned long long d = DEFAULT_ULONG (0);
        CHECK_CONV ();
        if (check_unsigned_range (minimum, G_MAXUINT, "minimum", attr_name) < 0
            || check_unsigned_range (maximum, G_MAXUINT, "maximum", attr_name) < 0
            || check_unsigned_bounds (minimum, maximum, attr_name) < 0
            || check_unsigned_range (d, maximum, "default", attr_name) < 0
            || check_unsigned_bounds (minimum, d, attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_uint (attr_name,
                                        nick,
                                        blurb,
                                        (guint)minimum,
                                        (guint)maximum,
                                        (guint)d,
                                        flags));
      }
    case G_TYPE_LONG:
      {
        long long minimum = MIN_LONG (G_MINLONG);
        long long maximum = MAX_LONG (G_MAXLONG);
        long long d = DEFAULT_LONG (0);
        CHECK_CONV ();
        if (check_signed_range (minimum, G_MINLONG, G_MAXLONG, "minimum", attr_name) < 0
            || check_signed_range (maximum, G_MINLONG, G_MAXLONG, "maximum", attr_name) < 0
            || check_signed_bounds (minimum, maximum, attr_name) < 0
            || check_signed_range (d, minimum, maximum, "default", attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_long (attr_name,
                                        nick,
                                        blurb,
                                        (glong)minimum,
                                        (glong)maximum,
                                        (glong)d,
                                        flags));
      }
    case G_TYPE_ULONG:
      {
        unsigned long long minimum = MIN_ULONG (0);
        unsigned long long maximum = MAX_ULONG (G_MAXULONG);
        unsigned long long d = DEFAULT_ULONG (0);
        CHECK_CONV ();
        if (check_unsigned_range (minimum, G_MAXULONG, "minimum", attr_name) < 0
            || check_unsigned_range (maximum, G_MAXULONG, "maximum", attr_name) < 0
            || check_unsigned_bounds (minimum, maximum, attr_name) < 0
            || check_unsigned_range (d, maximum, "default", attr_name) < 0
            || check_unsigned_bounds (minimum, d, attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_ulong (attr_name,
                                         nick,
                                         blurb,
                                         (gulong)minimum,
                                         (gulong)maximum,
                                         (gulong)d,
                                         flags));
      }
    case G_TYPE_INT64:
      {
        long long minimum = MIN_LONG (G_MININT64);
        long long maximum = MAX_LONG (G_MAXINT64);
        long long d = DEFAULT_LONG (0);
        CHECK_CONV ();
        if (check_signed_bounds (minimum, maximum, attr_name) < 0
            || check_signed_range (d, minimum, maximum, "default", attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_int64 (attr_name,
                                         nick,
                                         blurb,
                                         (gint64)minimum,
                                         (gint64)maximum,
                                         (gint64)d,
                                         flags));
      }
    case G_TYPE_UINT64:
      {
        unsigned long long minimum = MIN_ULONG (0);
        unsigned long long maximum = MAX_ULONG (G_MAXUINT64);
        unsigned long long d = DEFAULT_ULONG (0);
        CHECK_CONV ();
        if (check_unsigned_bounds (minimum, maximum, attr_name) < 0
            || check_unsigned_range (d, maximum, "default", attr_name) < 0
            || check_unsigned_bounds (minimum, d, attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_uint64 (attr_name,
                                          nick,
                                          blurb,
                                          (guint64)minimum,
                                          (guint64)maximum,
                                          (guint64)d,
                                          flags));
      }
    case G_TYPE_FLOAT:
      {
        double minimum = MIN_FLOAT (-G_MAXFLOAT);
        double maximum = MAX_FLOAT (G_MAXFLOAT);
        double d = DEFAULT_FLOAT (0.0);
        CHECK_CONV ();
        if (check_float_range (minimum, -G_MAXFLOAT, G_MAXFLOAT, "minimum", attr_name) < 0
            || check_float_range (maximum, -G_MAXFLOAT, G_MAXFLOAT, "maximum", attr_name) < 0
            || check_float_bounds (minimum, maximum, attr_name) < 0
            || check_float_range (d, minimum, maximum, "default", attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_float (attr_name,
                                         nick,
                                         blurb,
                                         (gfloat)minimum,
                                         (gfloat)maximum,
                                         (gfloat)d,
                                         flags));
      }
    case G_TYPE_DOUBLE:
      {
        double minimum = MIN_FLOAT (-G_MAXDOUBLE);
        double maximum = MAX_FLOAT (G_MAXDOUBLE);
        double d = DEFAULT_FLOAT (0.0);
        CHECK_CONV ();
        if (check_float_bounds (minimum, maximum, attr_name) < 0
            || check_float_range (d, minimum, maximum, "default", attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_double (attr_name, nick, blurb, minimum, maximum, d, flags));
      }
    case G_TYPE_STRING:
      {
        const char *d = has_default ? PyUnicode_AsUTF8 (default_o) : NULL;
        if (has_default && !d)
          return NULL;
        CHECK_PSPEC (g_param_spec_string (attr_name, nick, blurb, d, flags));
      }
    case G_TYPE_PARAM:
      CHECK_PSPEC (g_param_spec_param (attr_name, nick, blurb, gtype, flags));
    case G_TYPE_ENUM:
      {
        long long d = DEFAULT_LONG (0);
        CHECK_CONV ();
        if (check_signed_range (d, G_MININT, G_MAXINT, "default", attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_enum (attr_name, nick, blurb, gtype, (gint)d, flags));
      }
    case G_TYPE_FLAGS:
      {
        unsigned long long d = DEFAULT_ULONG (0);
        CHECK_CONV ();
        if (check_unsigned_range (d, G_MAXUINT, "default", attr_name) < 0)
          return NULL;
        CHECK_PSPEC (g_param_spec_flags (attr_name, nick, blurb, gtype, (guint)d, flags));
      }
    case G_TYPE_OBJECT:
    case G_TYPE_INTERFACE:
      CHECK_PSPEC (g_param_spec_object (attr_name, nick, blurb, gtype, flags));
    case G_TYPE_BOXED:
      CHECK_PSPEC (g_param_spec_boxed (attr_name, nick, blurb, gtype, flags));
    case G_TYPE_POINTER:
      CHECK_PSPEC (g_param_spec_pointer (attr_name, nick, blurb, flags));
    default:
      PyErr_Format (PyExc_TypeError, "unsupported property type for %s", attr_name);
      return NULL;
    }

#undef DEFAULT_LONG
#undef DEFAULT_ULONG
#undef DEFAULT_FLOAT
#undef MIN_LONG
#undef MAX_LONG
#undef MIN_ULONG
#undef MAX_ULONG
#undef MIN_FLOAT
#undef MAX_FLOAT
#undef CHECK_CONV
#undef CHECK_PSPEC
}

#include "GObject/Value.h"
#include "GObject/coercions.h"

typedef struct
{
  PyObject_HEAD GParamSpec *pspec;
} PyGIParamSpec;

static void
param_spec_dealloc (PyGIParamSpec *self)
{
  if (self->pspec != NULL)
    g_param_spec_unref (self->pspec);
  Py_TYPE (self)->tp_free ((PyObject *)self);
}

static PyObject *
param_spec_repr (PyGIParamSpec *self)
{
  const char *name = self->pspec != NULL ? g_param_spec_get_name (self->pspec) : NULL;
  const char *type_name = self->pspec != NULL ? G_OBJECT_TYPE_NAME (self->pspec) : NULL;
  PyObject *name_obj = name != NULL ? PyUnicode_FromString (name) : Py_NewRef (Py_None);
  if (name_obj == NULL)
    return NULL;
  PyObject *repr = PyUnicode_FromFormat ("<%s name=%R at %p>",
                                         type_name != NULL ? type_name : "GParamSpec",
                                         name_obj,
                                         self->pspec);
  Py_DECREF (name_obj);
  return repr;
}

static PyObject *
param_spec_get_name (PyGIParamSpec *self, void *closure G_GNUC_UNUSED)
{
  const char *name = self->pspec != NULL ? g_param_spec_get_name (self->pspec) : NULL;
  if (name == NULL)
    Py_RETURN_NONE;
  return PyUnicode_FromString (name);
}

static PyObject *
param_spec_get_nick (PyGIParamSpec *self, void *closure G_GNUC_UNUSED)
{
  const char *nick = self->pspec != NULL ? g_param_spec_get_nick (self->pspec) : NULL;
  if (nick == NULL)
    Py_RETURN_NONE;
  return PyUnicode_FromString (nick);
}

static PyObject *
param_spec_get_blurb (PyGIParamSpec *self, void *closure G_GNUC_UNUSED)
{
  const char *blurb = self->pspec != NULL ? g_param_spec_get_blurb (self->pspec) : NULL;
  if (blurb == NULL)
    Py_RETURN_NONE;
  return PyUnicode_FromString (blurb);
}

static PyObject *
param_spec_get_value_type (PyGIParamSpec *self, void *closure G_GNUC_UNUSED)
{
  if (self->pspec == NULL)
    Py_RETURN_NONE;
  /* GType is gsize (pointer-width); unsigned long is only 32-bit on LLP64
     (Windows), which truncates registered-type GTypes. */
  return PyLong_FromUnsignedLongLong ((unsigned long long)self->pspec->value_type);
}

static PyGetSetDef param_spec_getsets[] = {
  { "name", (getter)param_spec_get_name, NULL, NULL, NULL },
  { "nick", (getter)param_spec_get_nick, NULL, NULL, NULL },
  { "blurb", (getter)param_spec_get_blurb, NULL, NULL, NULL },
  { "value_type", (getter)param_spec_get_value_type, NULL, NULL, NULL },
  { NULL, NULL, NULL, NULL, NULL },
};

static PyTypeObject param_spec_type = {
  PyVarObject_HEAD_INIT (NULL, 0).tp_name = "ginext.private.ParamSpec",
  .tp_basicsize = sizeof (PyGIParamSpec),
  .tp_dealloc = (destructor)param_spec_dealloc,
  .tp_repr = (reprfunc)param_spec_repr,
  .tp_getset = param_spec_getsets,
  .tp_flags = Py_TPFLAGS_DEFAULT,
};

PyObject *
pygi_param_spec_new (GParamSpec *pspec)
{
  if (pspec == NULL)
    Py_RETURN_NONE;
  if (PyType_Ready (&param_spec_type) < 0)
    return NULL;
  PyGIParamSpec *self = PyObject_New (PyGIParamSpec, &param_spec_type);
  if (self == NULL)
    return NULL;
  self->pspec = g_param_spec_ref (pspec);
  return (PyObject *)self;
}

int
pygi_param_spec_from_py (PyObject *obj, GParamSpec **out_pspec)
{
  PyObject *repr = NULL;
  if (out_pspec == NULL)
    {
      PyErr_SetString (PyExc_SystemError, "pygi_param_spec_from_py: NULL out pointer");
      return -1;
    }
  *out_pspec = NULL;
  if (obj == Py_None)
    return 0;

  if (PyType_Ready (&param_spec_type) < 0)
    return -1;
  if (!PyObject_TypeCheck (obj, &param_spec_type))
    {
      repr = PyObject_Repr (obj);
      PyErr_Format (PyExc_TypeError,
                    "expected GObject.ParamSpec, got %.200s",
                    repr != NULL ? PyUnicode_AsUTF8 (repr) : Py_TYPE (obj)->tp_name);
      Py_XDECREF (repr);
      return -1;
    }

  *out_pspec = ((PyGIParamSpec *)obj)->pspec;
  return 0;
}

PyObject *
py_param_spec_from_gtype_name (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "Os", &gtype_obj, &name))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  if (gtype == G_TYPE_INVALID || !G_TYPE_IS_OBJECT (gtype))
    Py_RETURN_NONE;

  gpointer klass = g_type_class_ref (gtype);
  if (klass == NULL)
    Py_RETURN_NONE;
  GParamSpec *pspec = g_object_class_find_property (G_OBJECT_CLASS (klass), name);
  PyObject *out = pygi_param_spec_new (pspec);
  g_type_class_unref (klass);
  return out;
}

PyObject *
py_object_class_list_property_names (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &gtype_obj))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  if (gtype == G_TYPE_INVALID || !G_TYPE_IS_OBJECT (gtype))
    return PyList_New (0);

  gpointer klass = g_type_class_ref (gtype);
  if (klass == NULL)
    return PyList_New (0);

  guint n_props = 0;
  GParamSpec **props = g_object_class_list_properties (G_OBJECT_CLASS (klass), &n_props);
  PyObject *result = PyList_New ((Py_ssize_t)n_props);
  if (result == NULL)
    {
      g_free (props);
      g_type_class_unref (klass);
      return NULL;
    }
  for (guint i = 0; i < n_props; i++)
    {
      PyObject *name = PyUnicode_FromString (g_param_spec_get_name (props[i]));
      if (name == NULL)
        {
          Py_DECREF (result);
          g_free (props);
          g_type_class_unref (klass);
          return NULL;
        }
      PyList_SET_ITEM (result, (Py_ssize_t)i, name);
    }
  g_free (props);
  g_type_class_unref (klass);
  return result;
}

PyObject *
py_type_has_value_table (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &gtype_obj))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;

  return PyBool_FromLong (g_type_value_table_peek (gtype) != NULL);
}

PyObject *
py_interface_list_properties (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *gtype_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &gtype_obj))
    return NULL;

  GType gtype = G_TYPE_INVALID;
  if (pygi_gtype_from_py_object (gtype_obj, &gtype) != 0)
    return NULL;
  if (!G_TYPE_IS_INTERFACE (gtype))
    {
      PyErr_SetString (PyExc_TypeError, "GType is not an interface");
      return NULL;
    }

  gpointer iface = g_type_default_interface_ref (gtype);
  if (iface == NULL)
    {
      PyErr_SetString (PyExc_RuntimeError, "could not reference interface");
      return NULL;
    }

  guint n_props = 0;
  GParamSpec **props = g_object_interface_list_properties (iface, &n_props);
  PyObject *result = PyList_New (n_props);
  if (result == NULL)
    {
      g_free (props);
      g_type_default_interface_unref (iface);
      return NULL;
    }

  for (guint i = 0; i < n_props; i++)
    {
      PyObject *item = pygi_param_spec_new (props[i]);
      if (item == NULL)
        {
          Py_DECREF (result);
          g_free (props);
          g_type_default_interface_unref (iface);
          return NULL;
        }
      PyList_SET_ITEM (result, i, item);
    }

  g_free (props);
  g_type_default_interface_unref (iface);
  return result;
}


static GParamSpec *
param_spec_from_pointer_arg (PyObject *obj)
{
  if (PyObject_TypeCheck (obj, &param_spec_type))
    {
      PyGIParamSpec *ps = (PyGIParamSpec *)obj;
      if (ps->pspec == NULL)
        {
          PyErr_SetString (PyExc_ValueError, "pspec pointer is NULL");
          return NULL;
        }
      return ps->pspec;
    }
  unsigned long long raw = PyLong_AsUnsignedLongLong (obj);
  if (raw == (unsigned long long)-1 && PyErr_Occurred ())
    return NULL;
  if (raw == 0)
    {
      PyErr_SetString (PyExc_ValueError, "pspec pointer is NULL");
      return NULL;
    }
  return (GParamSpec *)(uintptr_t)raw;
}

PyObject *
py_param_spec_info (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  GParamSpec *pspec = param_spec_from_pointer_arg (ptr_obj);
  if (pspec == NULL)
    return NULL;

  return Py_BuildValue ("{s:K,s:s,s:z,s:z,s:I,s:K,s:z,s:K}",
                        "pointer",
                        (unsigned long long)(uintptr_t)pspec,
                        "name",
                        g_param_spec_get_name (pspec),
                        "nick",
                        g_param_spec_get_nick (pspec),
                        "blurb",
                        g_param_spec_get_blurb (pspec),
                        "flags",
                        (unsigned int)pspec->flags,
                        "value_type",
                        (unsigned long long)pspec->value_type,
                        "value_type_name",
                        g_type_name (pspec->value_type),
                        "owner_type",
                        (unsigned long long)pspec->owner_type);
}

PyObject *
py_param_spec_default_value (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  GParamSpec *pspec = param_spec_from_pointer_arg (ptr_obj);
  if (pspec == NULL)
    return NULL;

  const GValue *value = g_param_spec_get_default_value (pspec);
  if (value == NULL)
    Py_RETURN_NONE;
  return pygi_gvalue_value_to_py ((GValue *)value);
}

static PyObject *
numeric_info_new (PyObject *minimum, PyObject *maximum, PyObject *default_value)
{
  if (minimum == NULL || maximum == NULL || default_value == NULL)
    {
      Py_XDECREF (minimum);
      Py_XDECREF (maximum);
      Py_XDECREF (default_value);
      return NULL;
    }

  PyObject *dict = PyDict_New ();
  if (dict == NULL)
    {
      Py_DECREF (minimum);
      Py_DECREF (maximum);
      Py_DECREF (default_value);
      return NULL;
    }
  if (PyDict_SetItemString (dict, "minimum", minimum) < 0
      || PyDict_SetItemString (dict, "maximum", maximum) < 0
      || PyDict_SetItemString (dict, "default_value", default_value) < 0)
    {
      Py_DECREF (minimum);
      Py_DECREF (maximum);
      Py_DECREF (default_value);
      Py_DECREF (dict);
      return NULL;
    }

  Py_DECREF (minimum);
  Py_DECREF (maximum);
  Py_DECREF (default_value);
  return dict;
}

PyObject *
py_param_spec_numeric_info (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  PyObject *ptr_obj = NULL;
  if (!PyArg_ParseTuple (args, "O", &ptr_obj))
    return NULL;

  GParamSpec *pspec = param_spec_from_pointer_arg (ptr_obj);
  if (pspec == NULL)
    return NULL;

  GType value_type = pspec->value_type;
  if (value_type == G_TYPE_CHAR)
    {
      GParamSpecChar *p = G_PARAM_SPEC_CHAR (pspec);
      return numeric_info_new (PyLong_FromLong (p->minimum),
                               PyLong_FromLong (p->maximum),
                               PyLong_FromLong (p->default_value));
    }
  if (value_type == G_TYPE_UCHAR)
    {
      GParamSpecUChar *p = G_PARAM_SPEC_UCHAR (pspec);
      return numeric_info_new (PyLong_FromUnsignedLong (p->minimum),
                               PyLong_FromUnsignedLong (p->maximum),
                               PyLong_FromUnsignedLong (p->default_value));
    }
  if (value_type == G_TYPE_INT)
    {
      GParamSpecInt *p = G_PARAM_SPEC_INT (pspec);
      return numeric_info_new (PyLong_FromLong (p->minimum),
                               PyLong_FromLong (p->maximum),
                               PyLong_FromLong (p->default_value));
    }
  if (value_type == G_TYPE_UINT)
    {
      GParamSpecUInt *p = G_PARAM_SPEC_UINT (pspec);
      return numeric_info_new (PyLong_FromUnsignedLong (p->minimum),
                               PyLong_FromUnsignedLong (p->maximum),
                               PyLong_FromUnsignedLong (p->default_value));
    }
  if (value_type == G_TYPE_LONG)
    {
      GParamSpecLong *p = G_PARAM_SPEC_LONG (pspec);
      return numeric_info_new (PyLong_FromLong (p->minimum),
                               PyLong_FromLong (p->maximum),
                               PyLong_FromLong (p->default_value));
    }
  if (value_type == G_TYPE_ULONG)
    {
      GParamSpecULong *p = G_PARAM_SPEC_ULONG (pspec);
      return numeric_info_new (PyLong_FromUnsignedLong (p->minimum),
                               PyLong_FromUnsignedLong (p->maximum),
                               PyLong_FromUnsignedLong (p->default_value));
    }
  if (value_type == G_TYPE_INT64)
    {
      GParamSpecInt64 *p = G_PARAM_SPEC_INT64 (pspec);
      return numeric_info_new (PyLong_FromLongLong (p->minimum),
                               PyLong_FromLongLong (p->maximum),
                               PyLong_FromLongLong (p->default_value));
    }
  if (value_type == G_TYPE_UINT64)
    {
      GParamSpecUInt64 *p = G_PARAM_SPEC_UINT64 (pspec);
      return numeric_info_new (PyLong_FromUnsignedLongLong (p->minimum),
                               PyLong_FromUnsignedLongLong (p->maximum),
                               PyLong_FromUnsignedLongLong (p->default_value));
    }
  if (value_type == G_TYPE_FLOAT)
    {
      GParamSpecFloat *p = G_PARAM_SPEC_FLOAT (pspec);
      return numeric_info_new (PyFloat_FromDouble (p->minimum),
                               PyFloat_FromDouble (p->maximum),
                               PyFloat_FromDouble (p->default_value));
    }
  if (value_type == G_TYPE_DOUBLE)
    {
      GParamSpecDouble *p = G_PARAM_SPEC_DOUBLE (pspec);
      return numeric_info_new (PyFloat_FromDouble (p->minimum),
                               PyFloat_FromDouble (p->maximum),
                               PyFloat_FromDouble (p->default_value));
    }

  PyErr_Format (PyExc_TypeError,
                "GParamSpec value type %s is not numeric",
                g_type_name (value_type));
  return NULL;
}

