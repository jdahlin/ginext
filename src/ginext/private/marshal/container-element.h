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
#include "marshal/pygi-value.h"

#include <girepository/girepository.h>

typedef struct
{
  PyGIType type;
  gboolean is_string;
  gboolean is_direct;
} PyGIContainerElement;

int
pygi_container_element_init (PyGIContainerElement *element, GITypeInfo *ti);

gboolean
pygi_container_element_can_use_pointer_slot (const PyGIContainerElement *element);

int
pygi_container_element_pointer_from_py (const PyGIContainerElement *element,
                                        PyObject *py,
                                        GITransfer transfer,
                                        gpointer *out);

PyObject *
pygi_container_element_pointer_to_py (const PyGIContainerElement *element, gpointer ptr);

gboolean
pygi_container_element_can_use_hash_pointer (const PyGIContainerElement *element);

int
pygi_container_element_argument_from_py (const PyGIContainerElement *element,
                                         PyObject *py,
                                         GIArgument *out);

int
pygi_container_element_hash_pointer_from_argument (const PyGIContainerElement *element,
                                                   const GIArgument *arg,
                                                   GITransfer transfer,
                                                   gpointer *out);

PyObject *
pygi_container_element_hash_pointer_to_py (const PyGIContainerElement *element, gpointer ptr);

gsize
pygi_container_element_inline_size (const PyGIContainerElement *element);

int
pygi_container_element_inline_from_py (const PyGIContainerElement *element,
                                       PyObject *py,
                                       GITransfer transfer,
                                       void *dst);

PyObject *
pygi_container_element_inline_to_py (const PyGIContainerElement *element, const void *src);
