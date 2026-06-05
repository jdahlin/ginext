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

#include "common.h"

PyObject *
py_pointer_type_register_static (PyObject *m G_GNUC_UNUSED, PyObject *args)
{
  const char *name = NULL;
  if (!PyArg_ParseTuple (args, "s", &name))
    return NULL;

  /* Idempotent get-or-register: g_pointer_type_register_static() asserts the
   * name is not already registered, so a second call (e.g. if gi.repository's
   * module-level init runs twice in a process) would abort. Return the existing
   * GType when the name is already known. */
  GType gtype = g_type_from_name (name);
  if (gtype == 0)
    gtype = g_pointer_type_register_static (name);
  return PyLong_FromUnsignedLongLong ((unsigned long long)gtype);
}
