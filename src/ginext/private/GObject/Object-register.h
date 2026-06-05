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

#ifndef GINEXT_OBJECT_REGISTER_H
#define GINEXT_OBJECT_REGISTER_H

#include "common.h"

PyObject *
pygi_register_gobject_subclass_for_class (PyObject *cls,
                                          PyObject *annotations,
                                          const char *requested_name);

#endif /* GINEXT_OBJECT_REGISTER_H */
