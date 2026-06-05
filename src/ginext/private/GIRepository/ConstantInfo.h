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

PyObject *
py_constant_info_value (PyObject *module, PyObject *args);

/* GIRepository.ConstantInfo.value — reads a GIArgument union via
 * gi_constant_info_get_value() and converts the result to a Python object.
 * Accepts a GIRepository.ConstantInfo GObject wrapper as the sole argument. */
PyObject *
py_girepository_constant_info_get_value (PyObject *module, PyObject *args);
