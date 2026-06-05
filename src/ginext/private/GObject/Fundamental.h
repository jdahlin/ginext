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

#include <girepository/girepository.h>
#include <glib-object.h>

typedef gpointer (*PyGIRefFunc) (gpointer instance);
typedef void (*PyGIUnrefFunc) (gpointer instance);

/* Register custom ref/unref functions for a GType whose lifecycle functions
 * are not annotated in the GIR (e.g. GIBaseInfo). Must be called before any
 * attempt to ref/unref an instance of that type via pygi_instantiatable_ref. */
void
pygi_register_lifecycle_funcs (GType gtype, PyGIRefFunc ref_func, PyGIUnrefFunc unref_func);

int
pygi_instantiatable_ref (gpointer instance, GType gtype, gpointer *out_instance);
int
pygi_instantiatable_unref (gpointer instance, GType gtype);
PyObject *
pygi_fundamental_to_py (gpointer instance, GITransfer transfer, PyObject *wrapper_factory);
PyObject *
py_instantiatable_unref (PyObject *module, PyObject *args);
