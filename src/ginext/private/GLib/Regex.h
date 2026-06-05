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

/* True if `obj` is a compiled Python regex (re.Pattern instance). Never
 * raises; clears any transient import error. */
int
pygi_is_re_pattern (PyObject *obj);

/* Build a fresh GRegex (refcount 1, owned by the caller) from a Python
 * re.Pattern, translating the supported compile flags. Returns NULL and sets a
 * Python exception on failure (bad type, compile error). */
GRegex *
pygi_gregex_from_py_pattern (PyObject *pattern);
