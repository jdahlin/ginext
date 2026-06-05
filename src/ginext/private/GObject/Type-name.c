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

/* Auto-disambiguation for GType names.
 *
 * GType registration is one-way and process-global, so identically-named
 * classes from different test modules (or different invocations of the
 * same `class Foo(GObject)` literal) would collide. We append a `_N`
 * suffix to the user's preferred name until we find a free slot.
 *
 * The actually-registered name flows back through `GIMeta.type_name`,
 * so callers can see what they got if they care.
 */
#include "Type-name.h"

char *
unique_type_name (const char *requested)
{
  if (g_type_from_name (requested) == 0)
    return g_strdup (requested);
  for (guint n = 2; n < 1000000; n++)
    {
      char *candidate = g_strdup_printf ("%s_%u", requested, n);
      if (g_type_from_name (candidate) == 0)
        return candidate;
      g_free (candidate);
    }
  PyErr_Format (PyExc_RuntimeError,
                "GType namespace exhausted searching for free name based on '%s'",
                requested);
  return NULL;
}
