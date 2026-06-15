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

/* field_to_py / field_from_py are implemented in Boxed.c and used by the
 * descriptor getter/setter in field-descr.c. */
PyObject *
field_to_py (GITypeInfo *fti, char *base, size_t offset, PyObject *parent);

int
field_from_py (GITypeInfo *fti, char *base, size_t offset, PyObject *value);

PyObject *
union_interface_field_shadow_to_py (GITypeInfo *fti,
                                    char *base,
                                    size_t offset,
                                    PyObject *parent,
                                    const char *field_name);

/* Returns TRUE if the field type can be read/written. */
gboolean
field_to_py_supported (GITypeInfo *fti);

/* Returns non-zero if name is reserved (method or hidden field) on cls. */
int
record_class_field_name_reserved (PyObject *cls, const char *name);

/* Install PyGetSetDef descriptors for all fields in the struct/union info. */
PyObject *
py_record_install_field_descriptors (PyObject *module, PyObject *args);
