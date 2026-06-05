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

/* DateTime.c - accept stdlib datetime objects wherever GLib expects a
 * GDateTime, GDate or GTimeZone. A Python datetime/date/tzinfo handed to such
 * an argument or GObject property is converted to the GLib value on demand;
 * GLib values coming back out stay GLib.DateTime/Date/TimeZone. */
#include "GLib/DateTime.h"

#include <datetime.h>

static int dt_init_state = 0; /* 0=unattempted, 1=ready, -1=failed */
static GMutex dt_init_lock;

/* Import the datetime C API once (PyDateTimeAPI is per translation unit).
 * Returns 1 on success, 0 on failure (Python error set). */
static int
ensure_pydatetime (void)
{
  g_mutex_lock (&dt_init_lock);
  if (dt_init_state == 0)
    {
      PyDateTime_IMPORT;
      dt_init_state = PyDateTimeAPI != NULL ? 1 : -1;
    }
  int state = dt_init_state;
  g_mutex_unlock (&dt_init_lock);
  return state == 1 ? 1 : 0;
}

int
pygi_py_datetime_check (PyObject *obj)
{
  if (obj == NULL || !ensure_pydatetime ())
    {
      PyErr_Clear ();
      return 0;
    }
  return PyDateTime_Check (obj) ? 1 : 0;
}

int
pygi_py_date_check (PyObject *obj)
{
  if (obj == NULL || !ensure_pydatetime ())
    {
      PyErr_Clear ();
      return 0;
    }
  return PyDate_Check (obj) ? 1 : 0;
}

int
pygi_py_tzinfo_check (PyObject *obj)
{
  if (obj == NULL || !ensure_pydatetime ())
    {
      PyErr_Clear ();
      return 0;
    }
  return PyTZInfo_Check (obj) ? 1 : 0;
}

GTimeZone *
pygi_gtimezone_from_py (PyObject *obj)
{
  if (!ensure_pydatetime ())
    return NULL;
  if (!PyTZInfo_Check (obj))
    {
      PyErr_Format (PyExc_TypeError,
                    "expected a datetime.tzinfo, not %.200s",
                    Py_TYPE (obj)->tp_name);
      return NULL;
    }

  /* zoneinfo.ZoneInfo carries a `.key`: preserve the named zone. */
  if (PyObject_HasAttrString (obj, "key"))
    {
      PyObject *key = PyObject_GetAttrString (obj, "key");
      if (key != NULL && PyUnicode_Check (key))
        {
          const char *k = PyUnicode_AsUTF8 (key);
          GTimeZone *named = k != NULL ? g_time_zone_new_identifier (k) : NULL;
          Py_DECREF (key);
          if (named != NULL)
            return named;
        }
      else
        Py_XDECREF (key);
      PyErr_Clear ();
    }

  /* Otherwise use the fixed UTC offset. */
  PyObject *offset = PyObject_CallMethod (obj, "utcoffset", "O", Py_None);
  if (offset == NULL)
    return NULL;
  if (offset == Py_None)
    {
      Py_DECREF (offset);
      return g_time_zone_new_utc ();
    }
  long seconds = PyDateTime_DELTA_GET_DAYS (offset) * 86400
                 + PyDateTime_DELTA_GET_SECONDS (offset);
  Py_DECREF (offset);
  return g_time_zone_new_offset ((gint32)seconds);
}

static GTimeZone *
gtimezone_for_datetime (PyObject *dt)
{
  PyObject *tzinfo = PyObject_GetAttrString (dt, "tzinfo");
  if (tzinfo == NULL)
    return NULL;
  GTimeZone *tz;
  if (tzinfo == Py_None)
    tz = g_time_zone_new_local ();
  else
    tz = pygi_gtimezone_from_py (tzinfo);
  Py_DECREF (tzinfo);
  return tz;
}

GDateTime *
pygi_gdatetime_from_py (PyObject *obj)
{
  if (!ensure_pydatetime ())
    return NULL;
  if (!PyDateTime_Check (obj))
    {
      PyErr_Format (PyExc_TypeError,
                    "expected a datetime.datetime, not %.200s",
                    Py_TYPE (obj)->tp_name);
      return NULL;
    }

  GTimeZone *tz = gtimezone_for_datetime (obj);
  if (tz == NULL)
    return NULL;
  double seconds = PyDateTime_DATE_GET_SECOND (obj)
                   + PyDateTime_DATE_GET_MICROSECOND (obj) / 1e6;
  GDateTime *dt = g_date_time_new (tz,
                                   PyDateTime_GET_YEAR (obj),
                                   PyDateTime_GET_MONTH (obj),
                                   PyDateTime_GET_DAY (obj),
                                   PyDateTime_DATE_GET_HOUR (obj),
                                   PyDateTime_DATE_GET_MINUTE (obj),
                                   seconds);
  g_time_zone_unref (tz);
  if (dt == NULL)
    {
      PyErr_Format (PyExc_ValueError,
                    "datetime is out of range for GLib.DateTime");
      return NULL;
    }
  return dt;
}

GDate *
pygi_gdate_from_py (PyObject *obj)
{
  if (!ensure_pydatetime ())
    return NULL;
  if (!PyDate_Check (obj))
    {
      PyErr_Format (PyExc_TypeError,
                    "expected a datetime.date, not %.200s",
                    Py_TYPE (obj)->tp_name);
      return NULL;
    }
  return g_date_new_dmy ((GDateDay)PyDateTime_GET_DAY (obj),
                         (GDateMonth)PyDateTime_GET_MONTH (obj),
                         (GDateYear)PyDateTime_GET_YEAR (obj));
}
