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
