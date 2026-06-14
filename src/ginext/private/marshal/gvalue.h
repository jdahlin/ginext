/* Copyright 2026 Johan Dahlin
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#pragma once

#include "marshal/conversion.h"

PyObject *
pygi_gvalue_new_for_gtype (GType gtype);
PyObject *
pygi_gvalue_wrap_pointer (GValue *value);
