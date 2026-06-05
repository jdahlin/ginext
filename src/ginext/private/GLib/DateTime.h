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

#pragma once

#include <Python.h>
#include <glib.h>

/* Type checks for the stdlib datetime types. Never raise; clear any transient
 * import error and return 0 if the datetime C API is unavailable. */
int
pygi_py_datetime_check (PyObject *obj);
int
pygi_py_date_check (PyObject *obj);
int
pygi_py_tzinfo_check (PyObject *obj);

/* Build a fresh GLib value (owned by the caller) from the matching Python
 * object. Return NULL and set a Python exception on failure. */
GDateTime *
pygi_gdatetime_from_py (PyObject *obj);
GDate *
pygi_gdate_from_py (PyObject *obj);
GTimeZone *
pygi_gtimezone_from_py (PyObject *obj);
