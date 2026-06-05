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
#include <glib.h>

int
pygi_variant_from_py (PyObject *value, GIArgument *out);

PyObject *
pygi_variant_to_py (GITypeInfo *ti, GIArgument *arg, GITransfer transfer);

PyObject *
pygi_wrap_variant (GITypeInfo *ti, GVariant *variant, GITransfer transfer);

int
pygi_py_item_to_gvariant (PyObject *item, void **dst);
