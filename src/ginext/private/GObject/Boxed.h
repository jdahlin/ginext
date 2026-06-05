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
#include <glib-object.h>

typedef struct
{
  PyObject_HEAD gpointer boxed;
  GType gtype;
  int borrowed;
  int heap_allocated;
  gsize size;
  PyObject *py_dict;
  PyObject *parent;
} PyGIGLibBoxed;

extern PyTypeObject *pygi_gboxed_base_type;

int
pygi_boxed_check (PyObject *obj);

int
pygi_boxed_get (PyObject *obj, gpointer *out);

PyObject *
pygi_boxed_new (PyObject *cls, gpointer boxed, GType gtype, int transfer_full);

PyObject *
pygi_boxed_new_alias (PyObject *cls, gpointer boxed, GType gtype, PyObject *parent);

PyObject *
pygi_boxed_new_heap (PyObject *cls, gpointer boxed, GType gtype, gsize size);

/* Copy-on-retain for borrowed boxed aliases. A transfer-none boxed signal
 * argument is wrapped as an alias into GValue memory that is freed when the
 * emission returns; if a handler keeps the wrapper past its own scope the alias
 * would dangle. Promote such a wrapper to an owned g_boxed_copy so it survives.
 * No-op for owned wrappers, non-boxed objects, or aliases kept alive by a parent.
 * Returns TRUE if a copy was made. */
int
pygi_boxed_promote_borrowed_alias (PyObject *obj);

void
pygi_pybuffer_release_destroy_notify (gpointer data);
