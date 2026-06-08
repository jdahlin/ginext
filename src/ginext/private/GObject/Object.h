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

#include <glib-object.h>

extern PyTypeObject *pygi_gobject_type;
extern PyType_Spec GinextGObject_spec;

typedef struct
{
  PyObject_HEAD GObject *ptr;
  unsigned int flags;
  PyObject *weakreflist;
  GObject *construction_ptr;
  PyObject *construction_handlers;
} PyGIGObject;

enum
{
  PYGI_GOBJECT_WRAPPER_OWNS_REF = 1u << 0,
};

GObject *
pygi_gobject_get (PyObject *wrapper);
PyObject *
pygi_gobject_new (PyObject *type, GObject *object, int owned);
int
pygi_python_construction_active (void);
