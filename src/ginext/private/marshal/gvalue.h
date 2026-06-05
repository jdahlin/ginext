/* Copyright 2026 Johan Dahlin
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#pragma once

#include "marshal/conversion.h"

void
pygi_gvalue_set_to_py_fallback (PyObject *callback);
PyObject *
pygi_gvalue_get_to_py_fallback (void);
void
pygi_gvalue_set_from_py_converter (PyObject *callback);
PyObject *
pygi_gvalue_get_from_py_converter (void);
PyObject *
pygi_gvalue_new_for_gtype (GType gtype);
PyObject *
pygi_gvalue_wrap_pointer (GValue *value);
