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

#include <glib-object.h>

typedef enum
{
  PYGI_ARG_CLEANUP_NONE = 0,
  PYGI_ARG_CLEANUP_STRV = 1,
  PYGI_ARG_CLEANUP_FREE = 2,
  PYGI_ARG_CLEANUP_HASH_TABLE = 3,
  PYGI_ARG_CLEANUP_GVALUE = 4,
  PYGI_ARG_CLEANUP_GLIST = 5,
  PYGI_ARG_CLEANUP_GSLIST = 6,
  PYGI_ARG_CLEANUP_GARRAY = 7, /* g_array_unref() */
  PYGI_ARG_CLEANUP_GPTR_ARRAY = 8, /* g_ptr_array_unref() */
  PYGI_ARG_CLEANUP_GBYTE_ARRAY = 9, /* g_byte_array_unref() */
  PYGI_ARG_CLEANUP_FFI_CLOSURE = 10, /* pygi_callback_closure_destroy() */
  PYGI_ARG_CLEANUP_GVALUE_ARRAY = 11, /* g_value_unset each + g_free */
  PYGI_ARG_CLEANUP_GBYTES = 12, /* g_bytes_unref() */
  PYGI_ARG_CLEANUP_PYOBJECT = 13, /* Py_DECREF() */
  PYGI_ARG_CLEANUP_GERROR = 14, /* g_error_free() */
  PYGI_ARG_CLEANUP_GREGEX = 15, /* g_regex_unref() */
  PYGI_ARG_CLEANUP_GDATETIME = 16, /* g_date_time_unref() */
  PYGI_ARG_CLEANUP_GDATE = 17, /* g_date_free() */
  PYGI_ARG_CLEANUP_GTIMEZONE = 18, /* g_time_zone_unref() */
  PYGI_ARG_CLEANUP_PROPERTY_GVALUE = 19, /* GValue + nested conversion cleanup */
} PyGIArgCleanupKind;

typedef struct
{
  PyGIArgCleanupKind kind;
  void *ptr;
  gsize n;
} PyGIArgCleanup;

typedef struct
{
  GValue value;
  PyGIArgCleanup nested;
} PyGIPropertyGValueCleanup;

/* Free whatever the cleanup record owns, then reset it to PYGI_ARG_CLEANUP_NONE.
 * Safe to call on an already-cleared record. NULL-safe on `cleanup`. */
void
pygi_arg_cleanup_clear (PyGIArgCleanup *cleanup);

/* Apply pygi_arg_cleanup_clear() to each element of `cleanups[0..n_cleanups)`. */
void
pygi_arg_cleanups_clear (PyGIArgCleanup *cleanups, size_t n_cleanups);
