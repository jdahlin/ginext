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

typedef struct
{
  PyObject_HEAD
  gpointer instance;
  GType gtype;
} PyGIFundamental;

extern PyTypeObject *PyGIFundamental_Type;

static inline int
pygi_fundamental_check (PyObject *obj)
{
  return obj != NULL && PyGIFundamental_Type != NULL
         && PyObject_TypeCheck (obj, PyGIFundamental_Type);
}

static inline gpointer
pygi_fundamental_get_instance (PyObject *obj)
{
  return ((PyGIFundamental *)obj)->instance;
}

static inline GType
pygi_fundamental_get_gtype (PyObject *obj)
{
  return ((PyGIFundamental *)obj)->gtype;
}

void
pygi_register_lifecycle_funcs (GType gtype, PyGIRefFunc ref_func, PyGIUnrefFunc unref_func);

int
pygi_instantiatable_ref (gpointer instance, GType gtype, gpointer *out_instance);
int
pygi_instantiatable_unref (gpointer instance, GType gtype);

PyObject *
pygi_fundamental_new (PyTypeObject *type, gpointer instance, GType gtype);

PyObject *
pygi_fundamental_to_py (gpointer instance, GITransfer transfer, PyObject *wrapper_factory);

PyObject *
py_instantiatable_unref (PyObject *module, PyObject *args);
PyObject *
py_fundamental_from_pointer (PyObject *module, PyObject *args);
int
pygi_fundamental_type_init (void);
