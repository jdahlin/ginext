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

/* GValue ↔ Python converters for the GType fundamentals ginext supports.
 *
 * Each branch is small enough that a switch on G_TYPE_FUNDAMENTAL stays
 * the clearest dispatch. The error model: numeric overflow surfaces as
 * Python OverflowError, wrong-type writes (e.g. int → str) as TypeError
 * from the underlying Py* conversion. Unsupported GTypes raise
 * NotImplementedError so the gap is loud rather than silent.
 */
#include "Value.h"

#include "GObject/Boxed.h"
#include "GLib/Variant.h"
#include "GLib/Regex.h"
#include "GLib/DateTime.h"
#include "GObject/Object-info.h"
#include "marshal/gvalue.h"
#include "gimeta-helpers.h"

int
pygi_gvalue_wrapper_get (PyObject *obj, GValue **out)
{
  if (!pygi_boxed_check (obj))
    return 0;
  PyGIGLibBoxed *boxed = (PyGIGLibBoxed *)obj;
  if (boxed->gtype != G_TYPE_VALUE || boxed->boxed == NULL)
    return 0;
  if (out != NULL)
    *out = (GValue *)boxed->boxed;
  return 1;
}

int
pygi_py_to_gvalue_property (PyObject *py_value, GValue *out)
{
  GType vt = G_VALUE_TYPE (out);
  if (vt == G_TYPE_INVALID)
    {
      PyErr_SetString (PyExc_TypeError, "GValue is not initialized");
      return -1;
    }

  if (vt == G_TYPE_GTYPE)
    {
      GType v = G_TYPE_INVALID;
      if (pygi_gtype_from_py_object (py_value, &v) != 0)
        return -1;
      g_value_set_gtype (out, v);
      return 0;
    }
  if (vt == G_TYPE_VARIANT)
    {
      if (py_value != Py_None
          && !(PyObject_TypeCheck (py_value, pygi_gboxed_base_type)
               && ((PyGIGLibBoxed *)py_value)->gtype == G_TYPE_VARIANT))
        {
          PyErr_SetString (PyExc_TypeError, "GVariant value must be GLib.Variant or None");
          return -1;
        }
      void *variant = NULL;
      if (pygi_py_item_to_gvariant (py_value, &variant) != 0)
        return -1;
      g_value_take_variant (out, (GVariant *)variant);
      return 0;
    }

  if (vt == g_regex_get_type ())
    {
      if (Py_IsNone (py_value))
        {
          g_value_set_boxed (out, NULL);
          return 0;
        }
      if (pygi_is_re_pattern (py_value))
        {
          GRegex *regex = pygi_gregex_from_py_pattern (py_value);
          if (regex == NULL)
            return -1;
          g_value_take_boxed (out, regex);
          return 0;
        }
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (py_value, &boxed_ptr) == 0 && boxed_ptr != NULL)
        {
          g_value_set_boxed (out, boxed_ptr);
          return 0;
        }
      PyErr_Format (PyExc_TypeError,
                    "expected a re.Pattern for GLib.Regex property, not %.200s",
                    Py_TYPE (py_value)->tp_name);
      return -1;
    }

  if (vt == G_TYPE_DATE_TIME || vt == G_TYPE_DATE || vt == G_TYPE_TIME_ZONE)
    {
      if (Py_IsNone (py_value))
        {
          g_value_set_boxed (out, NULL);
          return 0;
        }
      gpointer built = NULL;
      if (vt == G_TYPE_DATE_TIME && pygi_py_datetime_check (py_value))
        built = pygi_gdatetime_from_py (py_value);
      else if (vt == G_TYPE_DATE && pygi_py_date_check (py_value))
        built = pygi_gdate_from_py (py_value);
      else if (vt == G_TYPE_TIME_ZONE && pygi_py_tzinfo_check (py_value))
        built = pygi_gtimezone_from_py (py_value);
      if (built != NULL)
        {
          g_value_take_boxed (out, built);
          return 0;
        }
      if (PyErr_Occurred ())
        return -1;
      gpointer boxed_ptr = NULL;
      if (pygi_boxed_get (py_value, &boxed_ptr) == 0 && boxed_ptr != NULL)
        {
          g_value_set_boxed (out, boxed_ptr);
          return 0;
        }
      PyErr_Format (PyExc_TypeError,
                    "expected a stdlib datetime/date/tzinfo or GLib value for "
                    "%s property, not %.200s",
                    g_type_name (vt),
                    Py_TYPE (py_value)->tp_name);
      return -1;
    }

  switch (G_TYPE_FUNDAMENTAL (vt))
    {
    case G_TYPE_BOOLEAN:
      {
        int b = PyObject_IsTrue (py_value);
        if (b < 0)
          return -1;
        g_value_set_boolean (out, b);
        return 0;
      }
    case G_TYPE_CHAR:
      {
        long v = PyLong_AsLong (py_value);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        if (v < G_MININT8 || v > G_MAXINT8)
          {
            PyErr_Format (PyExc_OverflowError, "%ld out of range for gchar", v);
            return -1;
          }
        g_value_set_schar (out, (gint8)v);
        return 0;
      }
    case G_TYPE_UCHAR:
      {
        unsigned long v = PyLong_AsUnsignedLong (py_value);
        if (v == (unsigned long)-1 && PyErr_Occurred ())
          return -1;
        if (v > G_MAXUINT8)
          {
            PyErr_Format (PyExc_OverflowError, "%lu out of range for guchar", v);
            return -1;
          }
        g_value_set_uchar (out, (guint8)v);
        return 0;
      }
    case G_TYPE_INT:
      {
        long v = PyLong_AsLong (py_value);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        if (v < G_MININT || v > G_MAXINT)
          {
            PyErr_Format (PyExc_OverflowError, "%ld out of range for gint", v);
            return -1;
          }
        g_value_set_int (out, (gint)v);
        return 0;
      }
    case G_TYPE_UINT:
      {
        unsigned long v = PyLong_AsUnsignedLong (py_value);
        if (v == (unsigned long)-1 && PyErr_Occurred ())
          return -1;
        if (v > G_MAXUINT)
          {
            PyErr_Format (PyExc_OverflowError, "%lu out of range for guint", v);
            return -1;
          }
        g_value_set_uint (out, (guint)v);
        return 0;
      }
    case G_TYPE_LONG:
      {
        long v = PyLong_AsLong (py_value);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        g_value_set_long (out, v);
        return 0;
      }
    case G_TYPE_ULONG:
      {
        unsigned long v = PyLong_AsUnsignedLong (py_value);
        if (v == (unsigned long)-1 && PyErr_Occurred ())
          return -1;
        g_value_set_ulong (out, v);
        return 0;
      }
    case G_TYPE_INT64:
      {
        long long v = PyLong_AsLongLong (py_value);
        if (v == -1 && PyErr_Occurred ())
          return -1;
        g_value_set_int64 (out, v);
        return 0;
      }
    case G_TYPE_UINT64:
      {
        unsigned long long v = PyLong_AsUnsignedLongLong (py_value);
        if (v == (unsigned long long)-1 && PyErr_Occurred ())
          return -1;
        g_value_set_uint64 (out, v);
        return 0;
      }
    case G_TYPE_FLOAT:
      {
        double v = PyFloat_AsDouble (py_value);
        if (v == -1.0 && PyErr_Occurred ())
          return -1;
        g_value_set_float (out, (gfloat)v);
        return 0;
      }
    case G_TYPE_DOUBLE:
      {
        double v = PyFloat_AsDouble (py_value);
        if (v == -1.0 && PyErr_Occurred ())
          return -1;
        g_value_set_double (out, v);
        return 0;
      }
    case G_TYPE_STRING:
      {
        if (Py_IsNone (py_value))
          {
            g_value_set_string (out, NULL);
            return 0;
          }
        if (PyBytes_Check (py_value))
          {
            g_value_set_string (out, PyBytes_AsString (py_value));
            return 0;
          }
        const char *s = PyUnicode_AsUTF8 (py_value);
        if (!s)
          return -1;
        g_value_set_string (out, s);
        return 0;
      }
    case G_TYPE_ENUM:
      {
        GValue temp = G_VALUE_INIT;
        if (pygi_py_to_gvalue_targeted (vt, py_value, &temp, "GValue") != 0)
          return -1;
        g_value_copy (&temp, out);
        g_value_unset (&temp);
        return 0;
      }
    case G_TYPE_FLAGS:
      {
        unsigned long v = PyLong_AsUnsignedLong (py_value);
        if (v == (unsigned long)-1 && PyErr_Occurred ())
          return -1;
        if (v > G_MAXUINT)
          {
            PyErr_Format (PyExc_OverflowError, "%lu out of range for flags", v);
            return -1;
          }
        g_value_set_flags (out, (guint)v);
        return 0;
      }
    case G_TYPE_INTERFACE:
    case G_TYPE_OBJECT:
      {
        if (Py_IsNone (py_value))
          {
            g_value_set_object (out, NULL);
            return 0;
          }
        GObject *object = pygi_gobject_get (py_value);
        if (object == NULL)
          return -1;
        if (object != NULL && !g_type_is_a (G_OBJECT_TYPE (object), vt))
          {
            PyErr_Format (PyExc_TypeError,
                          "expected %s, got %s",
                          g_type_name (vt),
                          g_type_name (G_OBJECT_TYPE (object)));
            return -1;
          }
        g_value_set_object (out, object);
        return 0;
      }
    }
  PyErr_Format (PyExc_NotImplementedError, "no GValue conversion for GType %s", g_type_name (vt));
  return -1;
}
