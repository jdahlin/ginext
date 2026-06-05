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

/* invoke/arg-cleanup.c - disposes per-argument cleanup records that
 * pygi_argument_from_py and the type-specific helpers register. */
#include "invoke/arg-cleanup.h"

#include "GObject/Closure.h"
#include <Python.h>
#include <glib-object.h>

void
pygi_arg_cleanup_clear (PyGIArgCleanup *cleanup)
{
  if (cleanup == NULL)
    return;
  switch (cleanup->kind)
    {
    case PYGI_ARG_CLEANUP_STRV:
      g_strfreev ((char **)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_FREE:
      g_free (cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_HASH_TABLE:
      g_hash_table_unref ((GHashTable *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GVALUE:
      {
        GValue *value = (GValue *)cleanup->ptr;
        if (value != NULL)
          {
            g_value_unset (value);
            g_free (value);
          }
        break;
      }
    case PYGI_ARG_CLEANUP_GLIST:
      g_list_free ((GList *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GSLIST:
      g_slist_free ((GSList *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GARRAY:
      g_array_unref ((GArray *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GPTR_ARRAY:
      g_ptr_array_unref ((GPtrArray *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GBYTE_ARRAY:
      g_byte_array_unref ((GByteArray *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GBYTES:
      g_bytes_unref ((GBytes *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GREGEX:
      g_regex_unref ((GRegex *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GDATETIME:
      g_date_time_unref ((GDateTime *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GDATE:
      g_date_free ((GDate *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GTIMEZONE:
      g_time_zone_unref ((GTimeZone *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_FFI_CLOSURE:
      pygi_callback_closure_destroy (cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_PYOBJECT:
      Py_XDECREF ((PyObject *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GERROR:
      g_error_free ((GError *)cleanup->ptr);
      break;
    case PYGI_ARG_CLEANUP_GVALUE_ARRAY:
      {
        GValue *values = (GValue *)cleanup->ptr;
        if (values != NULL)
          {
            for (gsize k = 0; k < cleanup->n; k++)
              g_value_unset (&values[k]);
            g_free (values);
          }
        break;
      }
    case PYGI_ARG_CLEANUP_NONE:
      break;
    }
  cleanup->kind = PYGI_ARG_CLEANUP_NONE;
  cleanup->ptr = NULL;
}

void
pygi_arg_cleanups_clear (PyGIArgCleanup *cleanups, size_t n_cleanups)
{
  for (size_t i = 0; i < n_cleanups; i++)
    pygi_arg_cleanup_clear (&cleanups[i]);
}
