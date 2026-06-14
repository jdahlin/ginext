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

#include <glib.h>
#include <Python.h>

/* Initialise the coercions dict.  Returns 0 on success, -1 on error. */
int pygi_coercions_init (void);

/* Register a Python callable as a coercion for a GType.
 * The callable signature is:  fn(obj: object) -> GLib wrapper
 * C code then extracts the boxed/object pointer from the returned wrapper.
 * Returns 0 on success, -1 on error. */
int pygi_coercion_register (GType gtype, PyObject *fn);

/* Call the coercion registered for @gtype with @obj.
 * Returns a new Python reference (the GLib wrapper) or NULL with no error set
 * if no coercion is registered.  A Python exception IS set on call failure. */
PyObject *pygi_call_coercion (GType gtype, PyObject *obj);
