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

#ifndef GINEXT_MAKE_PSPEC_H
#define GINEXT_MAKE_PSPEC_H

#include "common.h"

/* Build a GParamSpec from a Python Property descriptor. `attr_name` is
 * the annotation key (also used in error messages); `value_type` is the
 * annotation type (bool/int/float/str/...); `prop` is the Property
 * instance carrying nick/blurb/default/readonly/construct_only.
 * Returns NULL with a Python exception set on failure. */
GParamSpec *
make_pspec (const char *attr_name, PyObject *value_type, PyObject *prop);

#endif /* GINEXT_MAKE_PSPEC_H */
