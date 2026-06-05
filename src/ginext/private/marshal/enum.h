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

/* marshal/enum.h - int marshalling for enum/flags GI types.
 *
 * The Python heap-type builders for IntEnum / IntFlag live in
 * GObject/Enum.{c,h} and GObject/Flags.{c,h}; this file only holds
 * the inbound/outbound int conversion that the marshaller dispatches
 * to from the unified GIArgument <-> PyObject path.
 */
#pragma once

#include <Python.h>
#include <girepository/girepository.h>

int
pygi_enum_push_namespace_context (PyObject *namespace, PyObject **previous_out);
void
pygi_enum_pop_namespace_context (PyObject *previous);
PyObject *
pygi_namespace_context (void);

int
pygi_enum_info_from_py (PyObject *h, GIArgument *out);
PyObject *
pygi_enum_info_to_py (GITypeInfo *ti, GIArgument *arg);

int
pygi_flags_info_from_py (PyObject *h, GIArgument *out);
PyObject *
pygi_flags_info_to_py (GITypeInfo *ti, GIArgument *arg);
